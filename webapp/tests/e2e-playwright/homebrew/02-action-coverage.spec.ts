/**
 * 02-action-coverage.spec.ts
 *
 * 16 tests — one per action type supported by the homebrew rules engine.
 * Each test creates a character-subject rule with event=manual_trigger,
 * fires it via POST /characters/{id}/homebrew/manual-trigger/{ruleId},
 * then asserts the resulting STATE via API.
 *
 * Actions covered:
 *   roll_dice, lookup_table, match, if, set_property, inc_property,
 *   unequip, damage_character, heal_character, change_resource,
 *   restore_resource, apply_condition, remove_condition,
 *   apply_modifier_once, notify, add_history
 */

import { test, expect } from "./fixtures";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Build a manual_trigger rule. subject defaults to character. */
function manualRule(
  name: string,
  effects: any[],
  extra: { subject?: any; tables?: any[]; resources?: any[] } = {},
) {
  const dsl: any = {
    version: 1,
    subject: extra.subject ?? { type: "character" },
    triggers: [{ event: "manual_trigger", filters: [], effects }],
  };
  if (extra.tables) dsl.tables = extra.tables;
  if (extra.resources) dsl.resources = extra.resources;
  return { name, description: "audit action-coverage", enabled: true, dsl };
}

/**
 * Create rule + fire manual trigger; returns the notifications array.
 * The manual-trigger endpoint fires ALL manual_trigger rules on the character
 * when called with a specific rule ID — but since each test gets a fresh charId
 * the notifications only come from that test's rules.
 */
async function fireManual(
  apiRequest: any,
  charId: number,
  ruleBody: any,
): Promise<any[]> {
  const r = await apiRequest.post(`/characters/${charId}/homebrew/rules`, {
    data: ruleBody,
  });
  expect(
    r.status(),
    `rule create failed: ${r.status()} ${await r.text()}`,
  ).toBe(201);
  const ruleId = (await r.json()).id;
  const t = await apiRequest.post(
    `/characters/${charId}/homebrew/manual-trigger/${ruleId}`,
  );
  expect(
    t.ok(),
    `manual-trigger failed: ${t.status()} ${await t.text()}`,
  ).toBeTruthy();
  return (await t.json()).notifications ?? [];
}

/** Assert at least one notification contains the expected message string. */
function assertNotif(notifs: any[], msg: string) {
  expect(
    Array.isArray(notifs),
    `notifications must be an array, got: ${JSON.stringify(notifs)}`,
  ).toBeTruthy();
  if (!Array.isArray(notifs)) return;
  expect(
    notifs.some((n) => typeof n.message === "string" && n.message.includes(msg)),
    `Expected a notification containing "${msg}" but got: ${JSON.stringify(notifs)}`,
  ).toBeTruthy();
}

/** GET /characters/{charId} → full character object. */
async function getChar(apiRequest: any, charId: number) {
  const r = await apiRequest.get(`/characters/${charId}`);
  expect(r.ok(), `GET /characters/${charId} failed: ${r.status()}`).toBeTruthy();
  return r.json();
}

/** GET /characters/{charId}/homebrew/resources → resource array. */
async function getResources(apiRequest: any, charId: number) {
  const r = await apiRequest.get(`/characters/${charId}/homebrew/resources`);
  expect(r.ok(), `GET /homebrew/resources failed: ${r.status()}`).toBeTruthy();
  return (await r.json()) as any[];
}

/** GET /characters/{charId}/history → history entry array. */
async function getHistory(apiRequest: any, charId: number) {
  const r = await apiRequest.get(`/characters/${charId}/history`);
  expect(r.ok(), `GET /history failed: ${r.status()}`).toBeTruthy();
  return (await r.json()) as any[];
}

/** Set HP max + current via PATCH /characters/{charId}/hp (no homebrew events). */
async function setupHp(
  apiRequest: any,
  charId: number,
  max: number,
  current: number,
) {
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

test.describe("02-action-coverage", () => {

  // 1. notify
  test("notify emits a notification with the configured message", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "notify" });

    const notifs = await fireManual(
      apiRequest,
      charId,
      manualRule("Audit notify", [
        { action: "notify", severity: "info", message: "act-notify-fired" },
      ]),
    );

    assertNotif(notifs, "act-notify-fired");
  });

  // 2. add_history
  test("add_history writes a homebrew history entry", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "add_history" });

    await fireManual(
      apiRequest,
      charId,
      manualRule("Audit add_history", [
        { action: "add_history", description: "act-addhistory-marker" },
      ]),
    );

    const history = await getHistory(apiRequest, charId);
    const found = (history as any[]).some(
      (e: any) =>
        e.event_type === "homebrew" &&
        typeof e.description === "string" &&
        e.description.includes("act-addhistory-marker"),
    );
    expect(
      found,
      `Expected a homebrew history entry with "act-addhistory-marker", got: ${JSON.stringify(history)}`,
    ).toBeTruthy();
  });

  // 3. roll_dice
  test("roll_dice stores the roll result in a variable accessible to notify", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "roll_dice" });

    const notifs = await fireManual(
      apiRequest,
      charId,
      manualRule("Audit roll_dice", [
        { action: "roll_dice", notation: "1d1", store_as: "r" },
        { action: "notify", severity: "info", message: "rolled=$r" },
      ]),
    );

    // 1d1 always rolls 1 — deterministic
    assertNotif(notifs, "rolled=1");
  });

  // 4. lookup_table
  test("lookup_table resolves a cell value from a DSL table and stores it", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "lookup_table" });

    const notifs = await fireManual(
      apiRequest,
      charId,
      manualRule(
        "Audit lookup_table",
        [
          { action: "roll_dice", notation: "1d1", store_as: "roll" },
          {
            action: "lookup_table",
            table: "t",
            row: "alpha",
            col: "$roll",
            store_as: "res",
          },
          { action: "notify", severity: "info", message: "res=$res" },
        ],
        {
          tables: [
            {
              id: "t",
              row_axis: "r",
              col_axis: "c",
              col_bins: [[1, 1]],
              cells: { alpha: ["WIN"] },
            },
          ],
        },
      ),
    );

    assertNotif(notifs, "res=WIN");
  });

  // 5. match
  test("match branches into the matching case and executes its effects", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "match" });

    const notifs = await fireManual(
      apiRequest,
      charId,
      manualRule("Audit match", [
        { action: "roll_dice", notation: "1d1", store_as: "v" },
        {
          action: "match",
          value: "$v",
          cases: {
            "1": [{ action: "notify", severity: "info", message: "matched-one" }],
          },
        },
      ]),
    );

    assertNotif(notifs, "matched-one");
  });

  // 6. if
  test("if evaluates a condition and executes the then branch when true", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "if" });

    const notifs = await fireManual(
      apiRequest,
      charId,
      manualRule("Audit if", [
        {
          action: "if",
          cond: { path: "$character.id", op: "gt", value: 0 },
          then: [{ action: "notify", severity: "info", message: "then-branch" }],
          else: [{ action: "notify", severity: "info", message: "else-branch" }],
        },
      ]),
    );

    assertNotif(notifs, "then-branch");
    // Confirm the else branch was NOT taken
    expect(
      (notifs as any[]).some(
        (n: any) => typeof n.message === "string" && n.message.includes("else-branch"),
      ),
      `else-branch must NOT appear in notifications: ${JSON.stringify(notifs)}`,
    ).toBeFalsy();
  });

  // 7. set_property
  test("set_property writes hb_<key> into item_metadata on the subject item", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "set_property" });

    // Create the one weapon the item-subject rule will target
    const addItem = await apiRequest.post(`/characters/${charId}/items`, {
      data: { name: "PropBlade", item_type: "weapon", quantity: 1, is_equipped: false },
    });
    expect(addItem.status(), `POST /items failed: ${addItem.status()}`).toBe(201);

    await fireManual(
      apiRequest,
      charId,
      manualRule(
        "Audit set_property",
        [{ action: "set_property", target: "subject", key: "foo", value: "bar" }],
        { subject: { type: "item", filter: { item_types: ["weapon"] } } },
      ),
    );

    const char = await getChar(apiRequest, charId);
    const weapon = (char.items as any[]).find((i: any) => i.name === "PropBlade");
    expect(weapon, "PropBlade not found after set_property").toBeTruthy();
    expect(
      weapon.item_metadata?.hb_foo,
      `Expected item_metadata.hb_foo === "bar", got: ${JSON.stringify(weapon.item_metadata)}`,
    ).toBe("bar");
  });

  // 8. inc_property
  test("inc_property increments hb_<key> on the subject item by the specified delta", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "inc_property" });

    // Create the weapon; hb_count is absent (defaults to 0 for inc)
    const addItem = await apiRequest.post(`/characters/${charId}/items`, {
      data: { name: "CountBlade", item_type: "weapon", quantity: 1, is_equipped: false },
    });
    expect(addItem.status(), `POST /items failed: ${addItem.status()}`).toBe(201);

    await fireManual(
      apiRequest,
      charId,
      manualRule(
        "Audit inc_property",
        [{ action: "inc_property", target: "subject", key: "count", delta: 3 }],
        { subject: { type: "item", filter: { item_types: ["weapon"] } } },
      ),
    );

    const char = await getChar(apiRequest, charId);
    const weapon = (char.items as any[]).find((i: any) => i.name === "CountBlade");
    expect(weapon, "CountBlade not found after inc_property").toBeTruthy();
    expect(
      weapon.item_metadata?.hb_count,
      `Expected item_metadata.hb_count === 3, got: ${JSON.stringify(weapon.item_metadata)}`,
    ).toBe(3);
  });

  // 9. unequip
  test("unequip clears is_equipped and equipment_slot on the subject item", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "unequip" });

    // Create an already-equipped weapon
    const addItem = await apiRequest.post(`/characters/${charId}/items`, {
      data: {
        name: "UnequipBlade",
        item_type: "weapon",
        quantity: 1,
        is_equipped: true,
        equipment_slot: "main_hand",
      },
    });
    expect(addItem.status(), `POST /items failed: ${addItem.status()}`).toBe(201);

    await fireManual(
      apiRequest,
      charId,
      manualRule(
        "Audit unequip",
        [{ action: "unequip" }],
        { subject: { type: "item", filter: { item_types: ["weapon"] } } },
      ),
    );

    const char = await getChar(apiRequest, charId);
    const weapon = (char.items as any[]).find((i: any) => i.name === "UnequipBlade");
    expect(weapon, "UnequipBlade not found after unequip").toBeTruthy();
    expect(
      weapon.is_equipped,
      `Expected is_equipped === false, got: ${weapon.is_equipped}`,
    ).toBe(false);
    expect(
      weapon.equipment_slot ?? null,
      `Expected equipment_slot === null, got: ${weapon.equipment_slot}`,
    ).toBeNull();
  });

  // 10. damage_character
  test("damage_character reduces current_hit_points by the specified amount", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "damage_character" });

    await setupHp(apiRequest, charId, 20, 20);

    await fireManual(
      apiRequest,
      charId,
      manualRule("Audit damage_character", [
        { action: "damage_character", amount: 5 },
      ]),
    );

    const char = await getChar(apiRequest, charId);
    expect(
      char.current_hit_points,
      `Expected current_hit_points === 15, got: ${char.current_hit_points}`,
    ).toBe(15);
  });

  // 11. heal_character
  test("heal_character increases current_hit_points by the specified amount", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "heal_character" });

    await setupHp(apiRequest, charId, 20, 5);

    await fireManual(
      apiRequest,
      charId,
      manualRule("Audit heal_character", [
        { action: "heal_character", amount: 5 },
      ]),
    );

    const char = await getChar(apiRequest, charId);
    expect(
      char.current_hit_points,
      `Expected current_hit_points === 10, got: ${char.current_hit_points}`,
    ).toBe(10);
  });

  // 12. change_resource
  test("change_resource adjusts the current value of a homebrew resource by delta", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "change_resource" });

    // Resource materializes at current=max=3 when the rule is created
    await fireManual(
      apiRequest,
      charId,
      manualRule(
        "Audit change_resource",
        [{ action: "change_resource", key: "audit_cr", delta: -1 }],
        {
          resources: [
            { key: "audit_cr", name: "CR", max: 3, restoration_type: "none" },
          ],
        },
      ),
    );

    const resources = await getResources(apiRequest, charId);
    const res = (resources as any[]).find((r: any) => r.key === "audit_cr");
    expect(res, "audit_cr resource not found").toBeTruthy();
    expect(
      res.current,
      `Expected current === 2, got: ${res.current}`,
    ).toBe(2);
  });

  // 13. restore_resource
  test("restore_resource refills the resource to max when amount is 'max'", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "restore_resource" });

    // Step 1 — create the rule (resource materializes at current=max=3)
    const createResp = await apiRequest.post(
      `/characters/${charId}/homebrew/rules`,
      {
        data: manualRule(
          "Audit restore_resource",
          [{ action: "restore_resource", key: "audit_rr", amount: "max" }],
          {
            resources: [
              { key: "audit_rr", name: "RR", max: 3, restoration_type: "none" },
            ],
          },
        ),
      },
    );
    expect(
      createResp.status(),
      `rule create failed: ${createResp.status()} ${await createResp.text()}`,
    ).toBe(201);
    const ruleId = (await createResp.json()).id;

    // Step 2 — deplete the resource (PATCH does NOT fire the manual_trigger rule)
    const resources = await getResources(apiRequest, charId);
    const res = (resources as any[]).find((r: any) => r.key === "audit_rr");
    expect(res, "audit_rr resource not found after rule creation").toBeTruthy();
    const resId = res.id;

    const depleteResp = await apiRequest.patch(
      `/characters/${charId}/homebrew/resources/${resId}`,
      { data: { current: 0 } },
    );
    expect(
      depleteResp.status(),
      `PATCH /homebrew/resources failed: ${depleteResp.status()}`,
    ).toBe(200);

    // Step 3 — fire the manual trigger
    const triggerResp = await apiRequest.post(
      `/characters/${charId}/homebrew/manual-trigger/${ruleId}`,
    );
    expect(
      triggerResp.ok(),
      `manual-trigger failed: ${triggerResp.status()} ${await triggerResp.text()}`,
    ).toBeTruthy();

    // Step 4 — assert restored to max
    const resourcesAfter = await getResources(apiRequest, charId);
    const resAfter = (resourcesAfter as any[]).find(
      (r: any) => r.key === "audit_rr",
    );
    expect(resAfter, "audit_rr resource not found after restore").toBeTruthy();
    expect(
      resAfter.current,
      `Expected current === 3 (max) after restore_resource, got: ${resAfter.current}`,
    ).toBe(3);
  });

  // 14. apply_condition
  test("apply_condition inserts the key into the character conditions dict", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "apply_condition" });

    await fireManual(
      apiRequest,
      charId,
      manualRule("Audit apply_condition", [
        { action: "apply_condition", key: "custom:applytest" },
      ]),
    );

    const char = await getChar(apiRequest, charId);
    expect(
      Object.prototype.hasOwnProperty.call(char.conditions, "custom:applytest"),
      `Expected "custom:applytest" in conditions, got: ${JSON.stringify(char.conditions)}`,
    ).toBeTruthy();
  });

  // 15. remove_condition
  test("remove_condition deletes a previously applied condition key from the character", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "remove_condition" });

    // Step 1 — create rule1 (apply_condition seed) and capture its id
    const createRule1 = await apiRequest.post(
      `/characters/${charId}/homebrew/rules`,
      {
        data: manualRule("Audit seed remove_condition", [
          { action: "apply_condition", key: "custom:rmtest" },
        ]),
      },
    );
    expect(
      createRule1.status(),
      `rule1 create failed: ${createRule1.status()} ${await createRule1.text()}`,
    ).toBe(201);
    const rule1Id = (await createRule1.json()).id;

    // Fire rule1 to seed the condition
    const trigger1 = await apiRequest.post(
      `/characters/${charId}/homebrew/manual-trigger/${rule1Id}`,
    );
    expect(
      trigger1.ok(),
      `manual-trigger rule1 failed: ${trigger1.status()} ${await trigger1.text()}`,
    ).toBeTruthy();

    // Verify seed worked
    const charAfterSeed = await getChar(apiRequest, charId);
    expect(
      Object.prototype.hasOwnProperty.call(charAfterSeed.conditions, "custom:rmtest"),
      `Seed failed — "custom:rmtest" not in conditions: ${JSON.stringify(charAfterSeed.conditions)}`,
    ).toBeTruthy();

    // Step 2 — disable rule1 so it does NOT re-fire when rule2 is triggered
    const disableResp = await apiRequest.patch(
      `/characters/${charId}/homebrew/rules/${rule1Id}`,
      { data: { enabled: false } },
    );
    expect(
      disableResp.status(),
      `disable rule1 failed: ${disableResp.status()} ${await disableResp.text()}`,
    ).toBe(200);

    // Step 3 — create and fire rule2 (remove_condition)
    await fireManual(
      apiRequest,
      charId,
      manualRule("Audit remove_condition", [
        { action: "remove_condition", key: "custom:rmtest" },
      ]),
    );

    const charAfterRemove = await getChar(apiRequest, charId);
    expect(
      Object.prototype.hasOwnProperty.call(charAfterRemove.conditions, "custom:rmtest"),
      `Expected "custom:rmtest" to be removed from conditions, but still present: ${JSON.stringify(charAfterRemove.conditions)}`,
    ).toBeFalsy();
  });

  // 16. apply_modifier_once
  test("apply_modifier_once permanently increases hit_points max by the delta", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "apply_modifier_once" });

    // Set max to 20 so we can assert a precise final value
    await setupHp(apiRequest, charId, 20, 20);

    await fireManual(
      apiRequest,
      charId,
      manualRule("Audit apply_modifier_once", [
        {
          action: "apply_modifier_once",
          target: "character.hit_points_max",
          delta: 2,
          label: "+2 HP",
        },
      ]),
    );

    const char = await getChar(apiRequest, charId);
    expect(
      char.hit_points,
      `Expected hit_points (max) === 22 after apply_modifier_once, got: ${char.hit_points}`,
    ).toBe(22);
  });

});
