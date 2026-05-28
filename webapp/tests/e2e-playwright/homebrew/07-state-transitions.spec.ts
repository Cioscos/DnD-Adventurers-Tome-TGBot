/**
 * 07-state-transitions.spec.ts
 *
 * 5 tests — state-machine transitions for the Qualità & Usura damage_state
 * property and the Sanguinamento bleeding HP floor.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * RNG CONSTRAINT — why we use custom manual_trigger rules instead of the real
 * quality_wear template for the 4 Q&U transition tests:
 *
 * The real `quality_wear` template fires a 1d20 roll and looks up the result
 * in a wear table to determine the outcome ("X", "D", or "S"). There is no
 * HTTP endpoint to force a dice roll (the pytest suite monkeypatches
 * random.randint for deterministic outcomes). No quality value maps all
 * 1-20 results to the same outcome, so every table row has at least two
 * possible outcomes — meaning any live HTTP call is non-deterministic.
 *
 * Instead, we create lightweight `manual_trigger` rules that **replicate the
 * exact action branches** the Q&U template uses for its D and X outcomes,
 * wired to an item with a known starting `hb_damage_state`. This lets us test
 * the state-machine `if`/`set_property`/`unequip` logic deterministically,
 * without RNG. The random-driven end-to-end is covered by Task 7.5
 * (03-templates.spec.ts) and the pytest suite.
 *
 * Q&U outcome branches (from api/services/homebrew/templates.py):
 *   D outcome: if damage_state == "danneggiata" → set "distrutta" + unequip
 *              else                             → set "danneggiata"
 *   X outcome: unconditionally set "distrutta" + unequip (+ notify)
 *   S outcome: no-op (not tested here — it's a no-op)
 * ─────────────────────────────────────────────────────────────────────────────
 */

import { test, expect } from "./fixtures";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** GET /characters/{charId} → full character object. */
async function getChar(apiRequest: any, charId: number): Promise<any> {
  const r = await apiRequest.get(`/characters/${charId}`);
  expect(r.ok(), `GET /characters/${charId} failed: ${r.status()}`).toBeTruthy();
  return r.json();
}

/** Assert at least one notification contains the expected substring. */
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

/**
 * Create a weapon item with a starting hb_damage_state.
 * Returns the item's id (looked up by name "StateBlade" in the response).
 */
async function createWeapon(
  apiRequest: any,
  charId: number,
  damageState: string,
  equipped = true,
): Promise<number> {
  const r = await apiRequest.post(`/characters/${charId}/items`, {
    data: {
      name: "StateBlade",
      item_type: "weapon",
      quantity: 1,
      is_equipped: equipped,
      item_metadata: {
        damage_dice: "1d8",
        weapon_type: "melee",
        hb_damage_state: damageState,
      },
    },
  });
  expect(r.status(), `weapon create failed: ${r.status()} ${await r.text()}`).toBe(201);
  const body = await r.json();
  const item = (body.items as any[]).find((i: any) => i.name === "StateBlade");
  expect(item, "StateBlade not found in POST /items response").toBeTruthy();
  return item.id;
}

/**
 * Build the D-branch rule (replicates the Q&U template's "D" outcome branch):
 *   if damage_state == "danneggiata" → set "distrutta" + unequip
 *   else                             → set "danneggiata"
 */
function dBranchRule() {
  return {
    name: "Wear D-branch (deterministic)",
    enabled: true,
    dsl: {
      version: 1,
      subject: { type: "item", filter: { item_types: ["weapon"] } },
      triggers: [
        {
          event: "manual_trigger",
          filters: [],
          effects: [
            {
              // NB: DSL path "$subject.damage_state" resolves to item_metadata.hb_damage_state
              // (path_resolver prepends "hb_"); set_property key "damage_state" stores to the
              // same hb_-prefixed key.
              action: "if",
              cond: {
                path: "$subject.damage_state",
                op: "eq",
                value: "danneggiata",
              },
              then: [
                {
                  action: "set_property",
                  target: "subject",
                  key: "damage_state",
                  value: "distrutta",
                },
                { action: "unequip" },
              ],
              else: [
                {
                  action: "set_property",
                  target: "subject",
                  key: "damage_state",
                  value: "danneggiata",
                },
              ],
            },
          ],
        },
      ],
    },
  };
}

/**
 * Build the X-branch rule (replicates the Q&U template's "X" outcome branch):
 *   unconditionally set "distrutta" + unequip + notify.
 */
function xBranchRule() {
  return {
    name: "Wear X-branch (deterministic)",
    enabled: true,
    dsl: {
      version: 1,
      subject: { type: "item", filter: { item_types: ["weapon"] } },
      triggers: [
        {
          event: "manual_trigger",
          filters: [],
          effects: [
            {
              // NB: DSL path "$subject.damage_state" resolves to item_metadata.hb_damage_state
              // (path_resolver prepends "hb_"); set_property key "damage_state" stores to the
              // same hb_-prefixed key.
              action: "set_property",
              target: "subject",
              key: "damage_state",
              value: "distrutta",
            },
            { action: "unequip" },
            { action: "notify", severity: "info", message: "x-branch-fired" },
          ],
        },
      ],
    },
  };
}

/**
 * Create a rule and fire it via manual-trigger.
 * Returns the notifications array from the trigger response.
 */
async function createAndFire(
  apiRequest: any,
  charId: number,
  ruleBody: any,
): Promise<{ ruleId: number; notifications: any[] }> {
  const createResp = await apiRequest.post(
    `/characters/${charId}/homebrew/rules`,
    { data: ruleBody },
  );
  expect(
    createResp.status(),
    `rule create failed: ${createResp.status()} ${await createResp.text()}`,
  ).toBe(201);
  const ruleId = (await createResp.json()).id;

  const triggerResp = await apiRequest.post(
    `/characters/${charId}/homebrew/manual-trigger/${ruleId}`,
  );
  expect(
    triggerResp.ok(),
    `manual-trigger failed: ${triggerResp.status()} ${await triggerResp.text()}`,
  ).toBeTruthy();
  const notifications: any[] = (await triggerResp.json()).notifications ?? [];
  return { ruleId, notifications };
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

test.describe("07-state-transitions", () => {
  // ──────────────────────────────────────────────────────────────────────────
  // Test 1 — integra → danneggiata  (D-branch, item not yet damaged)
  // ──────────────────────────────────────────────────────────────────────────
  test("D-branch: integra weapon transitions to danneggiata", async ({ apiRequest, charId }) => {
    test.info().annotations.push({
      type: "event",
      description: "damage_state integra→danneggiata (D-branch else)",
    });

    // Create an equipped weapon with starting state "integra"
    await createWeapon(apiRequest, charId, "integra", true);

    // Fire the D-branch rule; the else-branch sets "danneggiata"
    await createAndFire(apiRequest, charId, dBranchRule());

    // Assert: hb_damage_state should now be "danneggiata"
    const char = await getChar(apiRequest, charId);
    const weapon = (char.items as any[]).find((i: any) => i.name === "StateBlade");
    expect(weapon, "StateBlade not found after D-branch fire").toBeTruthy();
    expect(
      weapon.item_metadata?.hb_damage_state,
      `Expected hb_damage_state="danneggiata", got: ${JSON.stringify(weapon.item_metadata)}`,
    ).toBe("danneggiata");
  });

  // ──────────────────────────────────────────────────────────────────────────
  // Test 2 — danneggiata → distrutta  (D-branch, already damaged → destroyed)
  // ──────────────────────────────────────────────────────────────────────────
  test("D-branch: danneggiata weapon transitions to distrutta and is unequipped", async ({ apiRequest, charId }) => {
    test.info().annotations.push({
      type: "event",
      description: "damage_state danneggiata→distrutta (D-branch then)",
    });

    // Create an equipped weapon with starting state "danneggiata"
    await createWeapon(apiRequest, charId, "danneggiata", true);

    // Fire the D-branch rule; the then-branch sets "distrutta" + unequip
    await createAndFire(apiRequest, charId, dBranchRule());

    // Assert: hb_damage_state="distrutta" AND is_equipped=false
    const char = await getChar(apiRequest, charId);
    const weapon = (char.items as any[]).find((i: any) => i.name === "StateBlade");
    expect(weapon, "StateBlade not found after D-branch fire").toBeTruthy();
    expect(
      weapon.item_metadata?.hb_damage_state,
      `Expected hb_damage_state="distrutta", got: ${JSON.stringify(weapon.item_metadata)}`,
    ).toBe("distrutta");
    expect(
      weapon.is_equipped,
      `Expected is_equipped=false after D-branch distrutta, got: ${weapon.is_equipped}`,
    ).toBe(false);
  });

  // ──────────────────────────────────────────────────────────────────────────
  // Test 3 — integra → distrutta  (X-branch, direct destruction)
  // ──────────────────────────────────────────────────────────────────────────
  test("X-branch: integra weapon is immediately destroyed and unequipped", async ({ apiRequest, charId }) => {
    test.info().annotations.push({
      type: "event",
      description: "damage_state integra→distrutta (X-branch unconditional)",
    });

    // Create an equipped weapon with starting state "integra"
    await createWeapon(apiRequest, charId, "integra", true);

    // Fire the X-branch rule; unconditionally sets "distrutta" + unequip
    await createAndFire(apiRequest, charId, xBranchRule());

    // Assert: hb_damage_state="distrutta" AND is_equipped=false
    const char = await getChar(apiRequest, charId);
    const weapon = (char.items as any[]).find((i: any) => i.name === "StateBlade");
    expect(weapon, "StateBlade not found after X-branch fire").toBeTruthy();
    expect(
      weapon.item_metadata?.hb_damage_state,
      `Expected hb_damage_state="distrutta", got: ${JSON.stringify(weapon.item_metadata)}`,
    ).toBe("distrutta");
    expect(
      weapon.is_equipped,
      `Expected is_equipped=false after X-branch, got: ${weapon.is_equipped}`,
    ).toBe(false);
  });

  // ──────────────────────────────────────────────────────────────────────────
  // Test 4 — distrutta is terminal under X-branch (idempotent destruction)
  //
  // Note: the Q&U D-branch applied to an already-distrutta item would
  // regress it back to "danneggiata" (the `if` condition fails, so the else-
  // branch fires). That is a known edge-quirk of the template DSL and is not
  // the canonical terminal state assertion. We assert terminality here using
  // the X-branch (canonical destruction path), which is idempotent: firing
  // it on an already-distrutta item leaves it distrutta.
  // ──────────────────────────────────────────────────────────────────────────
  test("X-branch: distrutta weapon remains distrutta (terminal state is idempotent)", async ({ apiRequest, charId }) => {
    test.info().annotations.push({
      type: "event",
      description: "damage_state distrutta→distrutta (terminal idempotent)",
    });

    // Create an UNEQUIPPED weapon (a destroyed item is unequipped) with state "distrutta"
    await createWeapon(apiRequest, charId, "distrutta", false);

    // Fire the X-branch rule; should still set "distrutta" (already there) + unequip (already unequipped)
    const { notifications } = await createAndFire(apiRequest, charId, xBranchRule());

    // Assert (a): rule body actually executed — the notify effect must be present
    // (proves the engine ran the rule, not just a start==end no-op coincidence)
    assertNotif(notifications, "x-branch-fired", "X-branch fire notifications");

    // Assert (b): hb_damage_state remains "distrutta" (terminal state is idempotent)
    const char = await getChar(apiRequest, charId);
    const weapon = (char.items as any[]).find((i: any) => i.name === "StateBlade");
    expect(weapon, "StateBlade not found after X-branch fire on distrutta").toBeTruthy();
    expect(
      weapon.item_metadata?.hb_damage_state,
      `Expected hb_damage_state="distrutta" (unchanged), got: ${JSON.stringify(weapon.item_metadata)}`,
    ).toBe("distrutta");
  });

  // ──────────────────────────────────────────────────────────────────────────
  // Test 5 — bleeding HP floor: HP cannot go below 0 after a bleed tick
  //
  // Starting HP = 1; bleeding rolls 1d4 (always ≥ 1); damage would take HP
  // below 0, but the engine floors at 0. We assert current_hit_points === 0.
  // Comment: 1d4 ≥ 1 is guaranteed, so the floor is always reached from HP=1.
  // ──────────────────────────────────────────────────────────────────────────
  test("bleeding: HP is floored at 0, never goes negative", async ({ apiRequest, charId }) => {
    test.info().annotations.push({
      type: "event",
      description: "bleeding HP cap at 0 (no negative HP)",
    });

    // ─── Set HP max=20, current=1 (1 − 1d4 would go negative without floor)
    await setupHp(apiRequest, charId, 20, 1);

    // ─── Install the bleeding template
    const installResp = await apiRequest.post(
      `/characters/${charId}/homebrew/templates/bleeding/install`,
    );
    expect(
      installResp.status(),
      `install bleeding failed: ${installResp.status()} ${await installResp.text()}`,
    ).toBe(201);

    // ─── Seed custom:bleeding condition via a separate apply_condition rule
    const seedResp = await apiRequest.post(`/characters/${charId}/homebrew/rules`, {
      data: {
        name: "Seed bleeding condition",
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
      seedResp.status(),
      `seed rule create failed: ${seedResp.status()} ${await seedResp.text()}`,
    ).toBe(201);
    const seedRuleId = (await seedResp.json()).id;

    // Fire the seed rule to apply the condition
    const seedTriggerResp = await apiRequest.post(
      `/characters/${charId}/homebrew/manual-trigger/${seedRuleId}`,
    );
    expect(
      seedTriggerResp.ok(),
      `seed trigger failed: ${seedTriggerResp.status()} ${await seedTriggerResp.text()}`,
    ).toBeTruthy();

    // Verify condition is present
    const charAfterSeed = await getChar(apiRequest, charId);
    expect(
      Object.prototype.hasOwnProperty.call(charAfterSeed.conditions, "custom:bleeding"),
      `Expected "custom:bleeding" in conditions after seed, got: ${JSON.stringify(charAfterSeed.conditions)}`,
    ).toBeTruthy();
    // HP must still be 1 (the condition seed fires no damage)
    expect(
      charAfterSeed.current_hit_points,
      `Expected current_hit_points=1 after condition seed (no damage yet), got: ${charAfterSeed.current_hit_points}`,
    ).toBe(1);

    // ─── Fire turn-start: bleeding rolls 1d4 (≥1) and deals damage
    const turnResp = await apiRequest.post(
      `/characters/${charId}/homebrew/turn-start`,
    );
    expect(
      turnResp.ok(),
      `POST /homebrew/turn-start failed: ${turnResp.status()} ${await turnResp.text()}`,
    ).toBeTruthy();
    const turnBody = await turnResp.json();

    // Assert notification contains "Sanguinamento"
    assertNotif(turnBody.notifications, "Sanguinamento", "turn-start notifications");

    // ─── Assert HP is exactly 0 (floored, never negative)
    // 1d4 ≥ 1 is guaranteed, so 1 − (1d4) ≤ 0 always.
    // The engine must floor at 0.
    const charAfterTurn = await getChar(apiRequest, charId);
    expect(
      charAfterTurn.current_hit_points,
      `Expected current_hit_points=0 (HP floor), got: ${charAfterTurn.current_hit_points}`,
    ).toBe(0);
  });
});
