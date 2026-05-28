/**
 * 06-error-cases.spec.ts
 *
 * 9 tests — error cases and boundary conditions for the homebrew rules engine.
 *
 * Cases covered:
 *   1. malformed DSL → 422
 *   2. disabled rule does not fire
 *   3. wrong event does not fire
 *   4. filter no-match does not fire
 *   5. cycle detection bounds recursion (MAX_DEPTH=8 backstop covered by backend unit test)
 *   6. subject filter mismatch → no fire (shield item vs weapon filter)
 *   7. missing subject → graceful skip (no items, weapon rule)
 *   8. multiple rules fire and accumulate
 *   9. resource not found → 404
 *
 * NOTE on depth-limit: The standalone "depth-limit-trigger" test is intentionally
 * folded into test 5's comment. The MAX_DEPTH=8 backstop is NOT triggerable over
 * HTTP because cycle detection stops single-rule self-recursion at depth 1, and a
 * multi-rule chain long enough to reach depth 9 explodes combinatorially. It is
 * covered by the backend unit test:
 *   tests/services/homebrew/test_dispatcher.py::test_dispatch_depth_exceeded_returns_empty_and_logs
 */

import { test, expect } from "./fixtures";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Create a homebrew rule and return its id. */
async function createRule(apiRequest: any, charId: number, body: any): Promise<number> {
  const r = await apiRequest.post(`/characters/${charId}/homebrew/rules`, { data: body });
  expect(r.status(), `rule create failed: ${r.status()} ${await r.text()}`).toBe(201);
  return (await r.json()).id;
}

/** Extract notification messages from a manual-trigger response (field: notifications). */
function manualNotifMessages(body: any): string[] {
  return ((body.notifications ?? []) as any[]).map((n: any) => String(n.message ?? ""));
}

/** Extract notification messages from a rest/hp/items response (field: homebrew_notifications). */
function restNotifMessages(body: any): string[] {
  if (!Array.isArray(body.homebrew_notifications)) return [];
  return (body.homebrew_notifications as any[]).map((n: any) => String(n.message ?? ""));
}

/** GET /characters/{charId} → full character object. */
async function getChar(apiRequest: any, charId: number): Promise<any> {
  const r = await apiRequest.get(`/characters/${charId}`);
  expect(r.ok(), `GET /characters/${charId} failed: ${r.status()}`).toBeTruthy();
  return r.json();
}

// ---------------------------------------------------------------------------
// Suite
// ---------------------------------------------------------------------------

test.describe("06-error-cases", () => {

  // 1. malformed DSL → 422
  test("malformed DSL (no triggers, no passive_modifiers) returns 422", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "malformed-dsl-422" });

    // A DSL with neither triggers nor passive_modifiers violates the engine's
    // "must declare at least one trigger or passive_modifier" rule → Pydantic 422.
    const resp = await apiRequest.post(`/characters/${charId}/homebrew/rules`, {
      data: {
        name: "Bad",
        enabled: true,
        dsl: {
          version: 1,
          subject: { type: "character" },
          // intentionally omits both triggers and passive_modifiers
        },
      },
    });

    expect(
      resp.status(),
      `Expected 422 for structurally-invalid DSL, got: ${resp.status()} — body: ${await resp.text()}`,
    ).toBe(422);
  });

  // 2. disabled rule does not fire
  test("disabled rule does not fire on matching event", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "disabled-rule-no-fire" });

    // Create a rule on long_rest_taken that is DISABLED
    await createRule(apiRequest, charId, {
      name: "Disabled Rest Rule",
      enabled: false,
      dsl: {
        version: 1,
        subject: { type: "character" },
        triggers: [
          {
            event: "long_rest_taken",
            filters: [],
            effects: [{ action: "notify", severity: "info", message: "disabled-should-not-fire" }],
          },
        ],
      },
    });

    const restResp = await apiRequest.post(`/characters/${charId}/rest`, {
      data: { rest_type: "long" },
    });
    expect(restResp.status(), `POST /rest failed: ${restResp.status()}`).toBe(200);
    const body = await restResp.json();

    const msgs = restNotifMessages(body);
    expect(
      msgs.some(m => m.includes("disabled-should-not-fire")),
      `Disabled rule must NOT fire, but found "disabled-should-not-fire" in: ${JSON.stringify(msgs)}`,
    ).toBeFalsy();
  });

  // 3. wrong event does not fire
  test("rule on long_rest_taken does not fire on short rest", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "wrong-event-no-fire" });

    // Create an ENABLED rule on long_rest_taken only
    await createRule(apiRequest, charId, {
      name: "Long Rest Only Rule",
      enabled: true,
      dsl: {
        version: 1,
        subject: { type: "character" },
        triggers: [
          {
            event: "long_rest_taken",
            filters: [],
            effects: [{ action: "notify", severity: "info", message: "long-only" }],
          },
        ],
      },
    });

    // Fire a SHORT rest — the long_rest_taken rule must NOT activate
    const restResp = await apiRequest.post(`/characters/${charId}/rest`, {
      data: { rest_type: "short" },
    });
    expect(restResp.status(), `POST /rest failed: ${restResp.status()}`).toBe(200);
    const body = await restResp.json();

    const msgs = restNotifMessages(body);
    expect(
      msgs.some(m => m.includes("long-only")),
      `long_rest_taken rule must NOT fire on short rest, but found "long-only" in: ${JSON.stringify(msgs)}`,
    ).toBeFalsy();
  });

  // 4. filter no-match does not fire
  test("filter with no-match condition prevents rule from firing on manual trigger", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "filter-no-match" });

    // Fresh character has speed=30; filter checks speed==999 (never true)
    const ruleId = await createRule(apiRequest, charId, {
      name: "Filter False Rule",
      enabled: true,
      dsl: {
        version: 1,
        subject: { type: "character" },
        triggers: [
          {
            event: "manual_trigger",
            filters: [{ path: "$character.speed", op: "eq", value: 999 }],
            effects: [{ action: "notify", severity: "info", message: "filter-false" }],
          },
        ],
      },
    });

    const triggerResp = await apiRequest.post(`/characters/${charId}/homebrew/manual-trigger/${ruleId}`);
    expect(triggerResp.status(), `POST /manual-trigger failed: ${triggerResp.status()}`).toBe(200);
    const body = await triggerResp.json();

    const msgs = manualNotifMessages(body);
    expect(
      msgs.some(m => m.includes("filter-false")),
      `Filter with speed==999 must NOT fire (speed is 30), but found "filter-false" in: ${JSON.stringify(msgs)}`,
    ).toBeFalsy();
  });

  // 5. cycle detection bounds recursion
  test("cycle detection prevents a damage_taken rule from re-triggering itself indefinitely", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "cycle-detection" });

    // NOTE on depth-limit: The MAX_DEPTH=8 backstop is NOT triggerable over HTTP.
    // Cycle detection stops single-rule self-recursion at depth 1: when the
    // damage_taken rule's effect (damage_character) re-emits damage_taken, the
    // dispatcher sees the rule id is already on the recursion stack and skips it.
    // This means the total damage is exactly 2 (1 from the PATCH + 1 from the rule's
    // single application), not infinite. The MAX_DEPTH=8 backstop is covered by:
    //   tests/services/homebrew/test_dispatcher.py::test_dispatch_depth_exceeded_returns_empty_and_logs

    // Set HP: max=50, current=50
    const setMaxResp = await apiRequest.patch(`/characters/${charId}/hp`, {
      data: { op: "set_max", value: 50 },
    });
    expect(setMaxResp.status(), `set_max failed: ${setMaxResp.status()}`).toBe(200);

    const setCurrentResp = await apiRequest.patch(`/characters/${charId}/hp`, {
      data: { op: "set_current", value: 50 },
    });
    expect(setCurrentResp.status(), `set_current failed: ${setCurrentResp.status()}`).toBe(200);

    // Create a rule: on damage_taken → damage_character by 1 (self-referential)
    await createRule(apiRequest, charId, {
      name: "Cycle Test Rule",
      enabled: true,
      dsl: {
        version: 1,
        subject: { type: "character" },
        triggers: [
          {
            event: "damage_taken",
            filters: [],
            effects: [{ action: "damage_character", amount: 1 }],
          },
        ],
      },
    });

    // Deal 1 damage via PATCH /hp — triggers damage_taken
    const dmgResp = await apiRequest.patch(`/characters/${charId}/hp`, {
      data: { op: "damage", value: 1 },
    });
    expect(dmgResp.status(), `damage op failed: ${dmgResp.status()}`).toBe(200);

    // Fetch current state
    const char = await getChar(apiRequest, charId);

    // Expected: 50 - 1 (PATCH) - 1 (rule fires once) = 48
    // Cycle detection stops the re-emitted damage_taken from re-triggering the rule.
    expect(
      char.current_hit_points,
      `Expected current_hit_points === 48 (50 - 1 PATCH - 1 rule), got: ${char.current_hit_points}. ` +
      `If this is < 48, cycle detection may not be working correctly.`,
    ).toBe(48);
  });

  // 6. subject filter mismatch → no fire
  test("item-subject rule with weapon filter does not fire when only a shield exists", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "subject-filter-mismatch" });

    // Create a rule targeting weapons only
    const ruleId = await createRule(apiRequest, charId, {
      name: "Weapon Only Rule",
      enabled: true,
      dsl: {
        version: 1,
        subject: { type: "item", filter: { item_types: ["weapon"] } },
        triggers: [
          {
            event: "manual_trigger",
            filters: [],
            effects: [{ action: "notify", severity: "info", message: "weapon-only" }],
          },
        ],
      },
    });

    // Create a SHIELD — does NOT match the weapon subject filter
    const addItemResp = await apiRequest.post(`/characters/${charId}/items`, {
      data: {
        name: "TestShield",
        item_type: "shield",
        quantity: 1,
        is_equipped: false,
      },
    });
    expect(addItemResp.status(), `POST /items failed: ${addItemResp.status()}`).toBe(201);

    const triggerResp = await apiRequest.post(`/characters/${charId}/homebrew/manual-trigger/${ruleId}`);
    expect(triggerResp.status(), `POST /manual-trigger failed: ${triggerResp.status()}`).toBe(200);
    const body = await triggerResp.json();

    const msgs = manualNotifMessages(body);
    expect(
      msgs.some(m => m.includes("weapon-only")),
      `weapon-only rule must NOT fire when only a shield exists; got: ${JSON.stringify(msgs)}`,
    ).toBeFalsy();
  });

  // 7. missing subject → graceful skip
  test("item-subject rule fires gracefully with no notification when no items exist", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "missing-subject-graceful-skip" });

    // NOTE: This models the "missing subject → graceful skip" case.
    // When no item matches the subject filter, the dispatcher finds no matching
    // subjects and the rule simply produces no effects — no crash, no error.

    // Create a weapon-subject rule — character has NO items at all
    const ruleId = await createRule(apiRequest, charId, {
      name: "Needs Weapon Rule",
      enabled: true,
      dsl: {
        version: 1,
        subject: { type: "item", filter: { item_types: ["weapon"] } },
        triggers: [
          {
            event: "manual_trigger",
            filters: [],
            effects: [{ action: "notify", severity: "info", message: "needs-weapon" }],
          },
        ],
      },
    });

    // Fire manual trigger — no weapon items exist, so rule has no matching subject
    const triggerResp = await apiRequest.post(`/characters/${charId}/homebrew/manual-trigger/${ruleId}`);
    expect(
      triggerResp.status(),
      `Expected 200 (graceful no-op), got: ${triggerResp.status()} — body: ${await triggerResp.text()}`,
    ).toBe(200);
    const body = await triggerResp.json();

    const msgs = manualNotifMessages(body);
    expect(
      msgs.some(m => m.includes("needs-weapon")),
      `needs-weapon rule must NOT fire when no weapons exist; got: ${JSON.stringify(msgs)}`,
    ).toBeFalsy();
  });

  // 8. multiple rules fire and accumulate
  test("two enabled rules on long_rest_taken both accumulate in homebrew_notifications", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "multiple-rules-accumulate" });

    // Create rule1 first (lower id → fires first, per id-ascending order)
    await createRule(apiRequest, charId, {
      name: "Rest Rule 1",
      enabled: true,
      dsl: {
        version: 1,
        subject: { type: "character" },
        triggers: [
          {
            event: "long_rest_taken",
            filters: [],
            effects: [{ action: "notify", severity: "info", message: "rest-rule-1" }],
          },
        ],
      },
    });

    // Create rule2 second (higher id → fires second)
    await createRule(apiRequest, charId, {
      name: "Rest Rule 2",
      enabled: true,
      dsl: {
        version: 1,
        subject: { type: "character" },
        triggers: [
          {
            event: "long_rest_taken",
            filters: [],
            effects: [{ action: "notify", severity: "info", message: "rest-rule-2" }],
          },
        ],
      },
    });

    // Fire long rest
    const restResp = await apiRequest.post(`/characters/${charId}/rest`, {
      data: { rest_type: "long" },
    });
    expect(restResp.status(), `POST /rest failed: ${restResp.status()}`).toBe(200);
    const body = await restResp.json();

    const msgs = restNotifMessages(body);

    expect(
      msgs.some(m => m.includes("rest-rule-1")),
      `Expected "rest-rule-1" in homebrew_notifications, got: ${JSON.stringify(msgs)}`,
    ).toBeTruthy();

    expect(
      msgs.some(m => m.includes("rest-rule-2")),
      `Expected "rest-rule-2" in homebrew_notifications, got: ${JSON.stringify(msgs)}`,
    ).toBeTruthy();

    // Rules fire in id-ascending order; rule1 was created before rule2, so its
    // notification appears first in the array.
    const idx1 = msgs.findIndex(m => m.includes("rest-rule-1"));
    const idx2 = msgs.findIndex(m => m.includes("rest-rule-2"));
    expect(
      idx1 < idx2,
      `Expected "rest-rule-1" (idx ${idx1}) to appear before "rest-rule-2" (idx ${idx2}) — rules fire in id-ascending order`,
    ).toBeTruthy();
  });

  // 9. resource not found → 404
  test("PATCH homebrew resource with nonexistent id returns 404", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "resource-not-found-404" });

    // Use an id that cannot exist for a valid owned character
    const resp = await apiRequest.patch(`/characters/${charId}/homebrew/resources/999999`, {
      data: { current: 1 },
    });

    expect(
      resp.status(),
      `Expected 404 for nonexistent homebrew resource id 999999, got: ${resp.status()} — body: ${await resp.text()}`,
    ).toBe(404);
  });

});
