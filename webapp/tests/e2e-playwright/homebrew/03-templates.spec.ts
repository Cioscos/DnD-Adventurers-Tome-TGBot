/**
 * 03-templates.spec.ts
 *
 * 4 lifecycle tests — one per hardcoded homebrew template:
 *   luck_points, bleeding, enchanted_weapon, quality_wear.
 *
 * CONSTRAINT: dice rolls cannot be forced over HTTP (the pytest suite monkeypatches
 * random.randint for deterministic outcomes). These tests assert:
 *   - deterministic state (luck_points)
 *   - statistical certainties (bleeding: 1d4 ≥ 1 always damages; enchanted: loop to
 *     hit at least one non-fumble attack in 6 tries)
 *   - pipeline invariants (quality_wear: outcome is valid-enum, request is 2xx)
 *
 * Notification field per endpoint:
 *   - POST /homebrew/manual-trigger/{id} → response.notifications
 *   - POST /homebrew/turn-start          → response.notifications
 *   - POST /rest                         → response.homebrew_notifications
 *   - PATCH /hp                          → response.homebrew_notifications
 *   - POST /items/{id}/attack            → response.homebrew_notifications
 */

import { test, expect } from "./fixtures";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Assert that at least one notification contains the expected substring. */
function assertNotif(
  notifs: any[] | undefined | null,
  substring: string,
  context = "notifications",
): void {
  expect(
    Array.isArray(notifs),
    `${context} must be an array, got: ${JSON.stringify(notifs)}`,
  ).toBeTruthy();
  if (!Array.isArray(notifs)) return;
  expect(
    notifs.some((n) => typeof n.message === "string" && n.message.includes(substring)),
    `Expected a notification containing "${substring}" but got: ${JSON.stringify(notifs)}`,
  ).toBeTruthy();
}

/** GET /characters/{charId} → full character object. */
async function getChar(apiRequest: any, charId: number): Promise<any> {
  const r = await apiRequest.get(`/characters/${charId}`);
  expect(r.ok(), `GET /characters/${charId} failed: ${r.status()}`).toBeTruthy();
  return r.json();
}

/** GET /characters/{charId}/homebrew/resources → resource array. */
async function getResources(apiRequest: any, charId: number): Promise<any[]> {
  const r = await apiRequest.get(`/characters/${charId}/homebrew/resources`);
  expect(r.ok(), `GET /homebrew/resources failed: ${r.status()}`).toBeTruthy();
  return (await r.json()) as any[];
}

/** PATCH /characters/{charId}/hp with set_max then set_current. */
async function setupHp(
  apiRequest: any,
  charId: number,
  max: number,
  current: number,
): Promise<void> {
  const r1 = await apiRequest.patch(`/characters/${charId}/hp`, {
    data: { op: "set_max", value: max },
  });
  expect(r1.status(), `set_max failed: ${r1.status()}`).toBe(200);
  const r2 = await apiRequest.patch(`/characters/${charId}/hp`, {
    data: { op: "set_current", value: current },
  });
  expect(r2.status(), `set_current failed: ${r2.status()}`).toBe(200);
}

// ---------------------------------------------------------------------------
// Suite
// ---------------------------------------------------------------------------

test.describe("03-templates", () => {

  // --------------------------------------------------------------------------
  // Test 1 — luck_points (fully deterministic)
  //
  // All outcomes are deterministic: install materializes 3/3, manual_trigger
  // decrements by exactly 1, long rest restores to exactly max.
  // --------------------------------------------------------------------------
  test("luck_points: install → spend → long rest restores", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "luck_points" });

    // ─── Install template (returns 201)
    const installResp = await apiRequest.post(
      `/characters/${charId}/homebrew/templates/luck_points/install`,
    );
    expect(
      installResp.status(),
      `install luck_points failed: ${installResp.status()} ${await installResp.text()}`,
    ).toBe(201);
    const ruleId = (await installResp.json()).id;

    // ─── Verify resource materialized at max (3/3)
    const resources = await getResources(apiRequest, charId);
    const luckRes = (resources as any[]).find((r: any) => r.key === "luck_points");
    expect(luckRes, "luck_points resource not found after install").toBeTruthy();
    expect(
      luckRes.current,
      `Expected current=3, got: ${luckRes.current}`,
    ).toBe(3);
    expect(
      luckRes.max,
      `Expected max=3, got: ${luckRes.max}`,
    ).toBe(3);

    // ─── Spend one luck point via manual_trigger
    const spendResp = await apiRequest.post(
      `/characters/${charId}/homebrew/manual-trigger/${ruleId}`,
    );
    expect(
      spendResp.ok(),
      `manual-trigger (spend) failed: ${spendResp.status()} ${await spendResp.text()}`,
    ).toBeTruthy();
    const spendBody = await spendResp.json();
    // manual-trigger returns { notifications: [...] }
    assertNotif(spendBody.notifications, "Punto Fortuna usato", "notifications");

    // Verify decremented to 2
    const resAfterSpend = await getResources(apiRequest, charId);
    const luckAfterSpend = (resAfterSpend as any[]).find((r: any) => r.key === "luck_points");
    expect(luckAfterSpend, "luck_points resource not found after spend").toBeTruthy();
    expect(
      luckAfterSpend.current,
      `Expected current=2 after spend, got: ${luckAfterSpend.current}`,
    ).toBe(2);

    // ─── Long rest restores to max
    const restResp = await apiRequest.post(`/characters/${charId}/rest`, {
      data: { rest_type: "long" },
    });
    expect(
      restResp.ok(),
      `POST /rest (long) failed: ${restResp.status()} ${await restResp.text()}`,
    ).toBeTruthy();
    const restBody = await restResp.json();
    // POST /rest returns homebrew_notifications
    assertNotif(restBody.homebrew_notifications, "Punti Fortuna ripristinati", "homebrew_notifications");

    // Verify restored to 3
    const resAfterRest = await getResources(apiRequest, charId);
    const luckAfterRest = (resAfterRest as any[]).find((r: any) => r.key === "luck_points");
    expect(luckAfterRest, "luck_points resource not found after rest").toBeTruthy();
    expect(
      luckAfterRest.current,
      `Expected current=3 after long rest, got: ${luckAfterRest.current}`,
    ).toBe(3);
  });

  // --------------------------------------------------------------------------
  // Test 2 — bleeding (statistically certain: 1d4 ≥ 1 always reduces HP)
  //
  // The bleeding trigger rolls 1d4 and deals that much damage. Since 1d4
  // always produces a value in [1,4], HP must drop by at least 1. We assert
  // current_hp < 20 (in range [16, 19]) after one turn-start tick.
  // --------------------------------------------------------------------------
  test("bleeding: install → apply condition → turn-start deals 1d4 damage", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "bleeding" });

    // ─── Set HP to 20/20
    await setupHp(apiRequest, charId, 20, 20);

    // ─── Install bleeding template
    const installResp = await apiRequest.post(
      `/characters/${charId}/homebrew/templates/bleeding/install`,
    );
    expect(
      installResp.status(),
      `install bleeding failed: ${installResp.status()} ${await installResp.text()}`,
    ).toBe(201);

    // ─── Seed the custom:bleeding condition via a separate manual_trigger rule
    // (turn_started fires on turn-start, not manual_trigger, so this seed rule
    //  won't interfere with the bleeding trigger itself)
    const seedRuleResp = await apiRequest.post(`/characters/${charId}/homebrew/rules`, {
      data: {
        name: "Seed bleeding condition",
        description: "Applies custom:bleeding condition for test setup",
        enabled: true,
        dsl: {
          version: 1,
          subject: { type: "character" },
          triggers: [
            {
              event: "manual_trigger",
              filters: [],
              effects: [{ action: "apply_condition", key: "custom:bleeding" }],
            },
          ],
        },
      },
    });
    expect(
      seedRuleResp.status(),
      `seed rule create failed: ${seedRuleResp.status()} ${await seedRuleResp.text()}`,
    ).toBe(201);
    const seedRuleId = (await seedRuleResp.json()).id;

    // Fire seed rule to apply condition
    const seedTriggerResp = await apiRequest.post(
      `/characters/${charId}/homebrew/manual-trigger/${seedRuleId}`,
    );
    expect(
      seedTriggerResp.ok(),
      `seed trigger failed: ${seedTriggerResp.status()} ${await seedTriggerResp.text()}`,
    ).toBeTruthy();

    // Verify the condition was applied
    const charAfterSeed = await getChar(apiRequest, charId);
    expect(
      Object.prototype.hasOwnProperty.call(charAfterSeed.conditions, "custom:bleeding"),
      `Expected "custom:bleeding" in conditions, got: ${JSON.stringify(charAfterSeed.conditions)}`,
    ).toBeTruthy();
    expect(
      charAfterSeed.current_hit_points,
      "HP should still be 20 after condition seed (no damage yet)",
    ).toBe(20);

    // ─── Fire turn-start: bleeding trigger runs, rolls 1d4, deals damage
    const turnResp = await apiRequest.post(`/characters/${charId}/homebrew/turn-start`);
    expect(
      turnResp.ok(),
      `POST /homebrew/turn-start failed: ${turnResp.status()} ${await turnResp.text()}`,
    ).toBeTruthy();
    const turnBody = await turnResp.json();
    // turn-start returns { notifications: [...] }
    assertNotif(turnBody.notifications, "Sanguinamento", "notifications");

    // ─── Verify HP dropped by 1d4 (always [1,4]) → must be in [16,19]
    const charAfterTurn = await getChar(apiRequest, charId);
    const hpAfter = charAfterTurn.current_hit_points;
    expect(
      hpAfter < 20,
      `Expected HP < 20 after bleeding tick (1d4 ≥ 1), got: ${hpAfter}`,
    ).toBeTruthy();
    expect(
      hpAfter >= 16,
      `Expected HP >= 16 after one 1d4 bleed tick (max loss = 4), got: ${hpAfter}`,
    ).toBeTruthy();
  });

  // --------------------------------------------------------------------------
  // Test 3 — enchanted_weapon (loop attacks to avoid the ~5% fumble flake)
  //
  // The enchanted_weapon trigger fires on attack_rolled when is_fumble=False
  // AND hb_enchanted=True. A natural-1 fumble (~5%) won't trigger it. We loop
  // up to 6 attacks and assert AT LEAST ONE produced a "fuoco" notification —
  // making the all-fumble probability ≈ 0.05^6 < 0.000000016 (astronomically
  // unlikely).
  // --------------------------------------------------------------------------
  test("enchanted_weapon: install → enchanted weapon attack fires fire damage", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "enchanted_weapon" });

    // ─── Install enchanted_weapon template FIRST
    const installResp = await apiRequest.post(
      `/characters/${charId}/homebrew/templates/enchanted_weapon/install`,
    );
    expect(
      installResp.status(),
      `install enchanted_weapon failed: ${installResp.status()} ${await installResp.text()}`,
    ).toBe(201);

    // ─── Create enchanted weapon AFTER install so _materialize_property_defaults
    // won't overwrite the explicitly-set hb_enchanted=true
    const createItemResp = await apiRequest.post(`/characters/${charId}/items`, {
      data: {
        name: "EnchBlade",
        item_type: "weapon",
        quantity: 1,
        is_equipped: true,
        item_metadata: { damage_dice: "1d8", weapon_type: "melee", hb_enchanted: true },
      },
    });
    expect(
      createItemResp.status(),
      `POST /items failed: ${createItemResp.status()} ${await createItemResp.text()}`,
    ).toBe(201);
    const createItemBody = await createItemResp.json();
    const enchWeapon = (createItemBody.items as any[]).find((i: any) => i.name === "EnchBlade");
    expect(enchWeapon, "EnchBlade not found in items after creation").toBeTruthy();
    const weaponId = enchWeapon.id;

    // Verify hb_enchanted survived (not overwritten to false by install's
    // materialization — _materialize_property_defaults only writes MISSING keys)
    expect(
      enchWeapon.item_metadata?.hb_enchanted,
      `Expected item_metadata.hb_enchanted === true, got: ${JSON.stringify(enchWeapon.item_metadata)}`,
    ).toBe(true);

    // ─── Loop up to 6 attacks; break early once a "fuoco" notification is seen.
    // A single non-fumble attack on an enchanted weapon MUST fire the notification.
    // The only way to miss is a natural-1 fumble (~5%). P(all 6 fumble) < 1.6e-8.
    let fireNotifSeen = false;
    for (let attempt = 1; attempt <= 6; attempt++) {
      const attackResp = await apiRequest.post(
        `/characters/${charId}/items/${weaponId}/attack`,
      );
      expect(
        attackResp.ok(),
        `attack attempt ${attempt} failed: ${attackResp.status()} ${await attackResp.text()}`,
      ).toBeTruthy();
      const attackBody = await attackResp.json();
      const notifs: any[] = attackBody.homebrew_notifications ?? [];
      if (notifs.some((n: any) => typeof n.message === "string" && n.message.includes("fuoco"))) {
        fireNotifSeen = true;
        break;
      }
    }

    expect(
      fireNotifSeen,
      "Expected at least one attack to produce a fire damage notification ('fuoco') in 6 attempts",
    ).toBeTruthy();
  });

  // --------------------------------------------------------------------------
  // Test 4 — quality_wear (invariant-based: outcome is random, pipeline must run clean)
  //
  // The wear template rolls 1d20 and looks up the result in the wear table to
  // determine "integra", "danneggiata", or "distrutta". We cannot force the
  // dice roll over HTTP (the pytest suite monkeypatches random.randint for exact
  // table-path assertions). Instead we verify:
  //   (a) Defaults are materialized on install: hb_quality="ordinaria", hb_damage_state="integra"
  //   (b) A critical-hit damage event (was_critical_hit=true) runs the full roll→table→match
  //       pipeline without a 500 error — the server must return 200.
  //   (c) The resulting hb_damage_state is one of the three valid enum values
  //       ["integra","danneggiata","distrutta"] — it may be any of them depending on
  //       the uncontrollable d20, but it MUST remain valid.
  // This proves the wear pipeline executes end-to-end via HTTP without ActionExecutionError.
  // --------------------------------------------------------------------------
  test("quality_wear: install materializes defaults → crit damage runs pipeline (invariant)", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "quality_wear" });

    // ─── Create an equipped weapon FIRST (install materializes defaults onto
    // existing matching items via _materialize_property_defaults)
    const createItemResp = await apiRequest.post(`/characters/${charId}/items`, {
      data: {
        name: "WearBlade",
        item_type: "weapon",
        quantity: 1,
        is_equipped: true,
        item_metadata: { damage_dice: "1d8", weapon_type: "melee" },
      },
    });
    expect(
      createItemResp.status(),
      `POST /items failed: ${createItemResp.status()} ${await createItemResp.text()}`,
    ).toBe(201);
    const createItemBody = await createItemResp.json();
    const wearWeapon = (createItemBody.items as any[]).find((i: any) => i.name === "WearBlade");
    expect(wearWeapon, "WearBlade not found in items after creation").toBeTruthy();

    // ─── Install quality_wear template
    const installResp = await apiRequest.post(
      `/characters/${charId}/homebrew/templates/quality_wear/install`,
    );
    expect(
      installResp.status(),
      `install quality_wear failed: ${installResp.status()} ${await installResp.text()}`,
    ).toBe(201);

    // ─── Assert defaults were materialized onto the existing weapon
    const charAfterInstall = await getChar(apiRequest, charId);
    const weaponAfterInstall = (charAfterInstall.items as any[]).find(
      (i: any) => i.name === "WearBlade",
    );
    expect(weaponAfterInstall, "WearBlade not found after install").toBeTruthy();
    expect(
      weaponAfterInstall.item_metadata?.hb_quality,
      `Expected hb_quality="ordinaria" after install, got: ${JSON.stringify(weaponAfterInstall.item_metadata)}`,
    ).toBe("ordinaria");
    expect(
      weaponAfterInstall.item_metadata?.hb_damage_state,
      `Expected hb_damage_state="integra" after install, got: ${JSON.stringify(weaponAfterInstall.item_metadata)}`,
    ).toBe("integra");

    // ─── Set HP to 20/20 so the character is alive when we trigger damage
    await setupHp(apiRequest, charId, 20, 20);

    // ─── Trigger the damage_taken quality_wear handler via a critical hit.
    // The damage_taken trigger fires when was_critical_hit=true and the subject
    // item has_property "quality" AND is_equipped=true.
    // We assert only that the server returns 200 and hb_damage_state is valid —
    // the exact value depends on the uncontrollable 1d20. The pytest suite
    // (test_template_quality_wear.py) covers exact table-path outcomes by monkeypatching
    // random.randint; here we prove the full pipeline executes without crashing.
    const critResp = await apiRequest.patch(`/characters/${charId}/hp`, {
      data: { op: "damage", value: 5, was_critical_hit: true },
    });
    expect(
      critResp.status(),
      `PATCH /hp (crit damage) failed: ${critResp.status()} ${await critResp.text()}`,
    ).toBe(200);

    // ─── Verify hb_damage_state is one of the three valid enum values.
    // (Exact value is non-deterministic due to the 1d20 roll — see constraint above.)
    const charAfterCrit = await getChar(apiRequest, charId);
    const weaponAfterCrit = (charAfterCrit.items as any[]).find(
      (i: any) => i.name === "WearBlade",
    );
    expect(weaponAfterCrit, "WearBlade not found after crit damage").toBeTruthy();
    const damageState = weaponAfterCrit.item_metadata?.hb_damage_state;
    const validStates = ["integra", "danneggiata", "distrutta"];
    expect(
      validStates.includes(damageState),
      `Expected hb_damage_state to be one of ${JSON.stringify(validStates)}, got: "${damageState}"`,
    ).toBeTruthy();
  });

});
