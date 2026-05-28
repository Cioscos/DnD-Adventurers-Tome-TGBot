/**
 * 05-filters.spec.ts
 *
 * 8 tests — one per filter operator supported by the homebrew rules engine.
 * Operators: eq, neq, lt, lte, gt, gte, in, has_property
 *
 * Strategy:
 *   For each operator, create TWO rules with the same character + manual_trigger:
 *   - Rule A: filter MATCHES → notify message "HIT-<op>"
 *   - Rule B: filter does NOT match → notify message "MISS-<op>"
 *   Fire ONE manual-trigger → both rules evaluated → response.notifications contains
 *   both "HIT-<op>" (must) and NOT "MISS-<op>" (must-not).
 *   This proves the operator distinguishes matching from non-matching conditions.
 *
 * Key fact:
 *   Fresh character always has speed === 30 (stable default).
 *   Character context exposes $character.speed.
 *   Use for all numeric/equality operators (eq, neq, lt, lte, gt, gte, in).
 *
 * Special case — has_property:
 *   Checks if a property KEY exists on subject.
 *   Use an item subject + a weapon carrying item_metadata: { hb_foo: "present" }.
 *   Filter: { path: "$subject", op: "has_property", value: "foo" } checks for key.
 */

import { test, expect } from "./fixtures";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Build a rule with a given filter + manual_trigger.
 * Subject defaults to character; can override.
 */
function filterRule(
  name: string,
  message: string,
  filter: any,
  subject: any = { type: "character" }
) {
  return {
    name,
    enabled: true,
    dsl: {
      version: 1,
      subject,
      triggers: [
        {
          event: "manual_trigger",
          filters: [filter],
          effects: [
            { action: "notify", severity: "info", message },
          ],
        },
      ],
    },
  };
}

/** Create a rule via POST /characters/{charId}/homebrew/rules. */
async function createRule(apiRequest: any, charId: number, body: any): Promise<number> {
  const r = await apiRequest.post(`/characters/${charId}/homebrew/rules`, { data: body });
  expect(r.status(), `rule create failed: ${r.status()} ${await r.text()}`).toBe(201);
  return (await r.json()).id;
}

/** Extract notification messages from manual-trigger response. */
function notifMessages(body: any): string[] {
  return (body.notifications ?? []).map((n: any) => n.message as string);
}

// ---------------------------------------------------------------------------
// Suite
// ---------------------------------------------------------------------------

test.describe("05-filters", () => {

  // 1. eq — equality check
  test("eq operator matches when values are equal", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "eq" });

    const filterA = { path: "$character.speed", op: "eq", value: 30 };
    const filterB = { path: "$character.speed", op: "eq", value: 99 };

    const ruleAId = await createRule(apiRequest, charId, filterRule("eq-match", "HIT-eq", filterA));
    await createRule(apiRequest, charId, filterRule("eq-nomatch", "MISS-eq", filterB));

    // Fire manual-trigger (endpoint fires ALL manual_trigger rules for this character)
    const triggerResp = await apiRequest.post(`/characters/${charId}/homebrew/manual-trigger/${ruleAId}`);
    expect(triggerResp.ok(), `manual-trigger failed: ${triggerResp.status()}`).toBeTruthy();
    const body = await triggerResp.json();

    const msgs = notifMessages(body);
    expect(msgs.some(m => m.includes("HIT-eq")), `expected HIT-eq; got ${JSON.stringify(msgs)}`).toBeTruthy();
    expect(msgs.some(m => m.includes("MISS-eq")), `did not expect MISS-eq; got ${JSON.stringify(msgs)}`).toBeFalsy();
  });

  // 2. neq — inequality check
  test("neq operator matches when values differ", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "neq" });

    const filterA = { path: "$character.speed", op: "neq", value: 99 };
    const filterB = { path: "$character.speed", op: "neq", value: 30 };

    const ruleAId = await createRule(apiRequest, charId, filterRule("neq-match", "HIT-neq", filterA));
    await createRule(apiRequest, charId, filterRule("neq-nomatch", "MISS-neq", filterB));

    const triggerResp = await apiRequest.post(`/characters/${charId}/homebrew/manual-trigger/${ruleAId}`);
    expect(triggerResp.ok(), `manual-trigger failed: ${triggerResp.status()}`).toBeTruthy();
    const body = await triggerResp.json();

    const msgs = notifMessages(body);
    expect(msgs.some(m => m.includes("HIT-neq")), `expected HIT-neq; got ${JSON.stringify(msgs)}`).toBeTruthy();
    expect(msgs.some(m => m.includes("MISS-neq")), `did not expect MISS-neq; got ${JSON.stringify(msgs)}`).toBeFalsy();
  });

  // 3. lt — less than
  test("lt operator matches when lhs < rhs", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "lt" });

    // speed is 30; 30 < 31 is true; 30 < 30 is false
    const filterA = { path: "$character.speed", op: "lt", value: 31 };
    const filterB = { path: "$character.speed", op: "lt", value: 30 };

    const ruleAId = await createRule(apiRequest, charId, filterRule("lt-match", "HIT-lt", filterA));
    await createRule(apiRequest, charId, filterRule("lt-nomatch", "MISS-lt", filterB));

    const triggerResp = await apiRequest.post(`/characters/${charId}/homebrew/manual-trigger/${ruleAId}`);
    expect(triggerResp.ok(), `manual-trigger failed: ${triggerResp.status()}`).toBeTruthy();
    const body = await triggerResp.json();

    const msgs = notifMessages(body);
    expect(msgs.some(m => m.includes("HIT-lt")), `expected HIT-lt; got ${JSON.stringify(msgs)}`).toBeTruthy();
    expect(msgs.some(m => m.includes("MISS-lt")), `did not expect MISS-lt; got ${JSON.stringify(msgs)}`).toBeFalsy();
  });

  // 4. lte — less than or equal
  test("lte operator matches when lhs <= rhs", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "lte" });

    // speed is 30; 30 <= 30 is true; 30 <= 29 is false
    const filterA = { path: "$character.speed", op: "lte", value: 30 };
    const filterB = { path: "$character.speed", op: "lte", value: 29 };

    const ruleAId = await createRule(apiRequest, charId, filterRule("lte-match", "HIT-lte", filterA));
    await createRule(apiRequest, charId, filterRule("lte-nomatch", "MISS-lte", filterB));

    const triggerResp = await apiRequest.post(`/characters/${charId}/homebrew/manual-trigger/${ruleAId}`);
    expect(triggerResp.ok(), `manual-trigger failed: ${triggerResp.status()}`).toBeTruthy();
    const body = await triggerResp.json();

    const msgs = notifMessages(body);
    expect(msgs.some(m => m.includes("HIT-lte")), `expected HIT-lte; got ${JSON.stringify(msgs)}`).toBeTruthy();
    expect(msgs.some(m => m.includes("MISS-lte")), `did not expect MISS-lte; got ${JSON.stringify(msgs)}`).toBeFalsy();
  });

  // 5. gt — greater than
  test("gt operator matches when lhs > rhs", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "gt" });

    // speed is 30; 30 > 29 is true; 30 > 30 is false
    const filterA = { path: "$character.speed", op: "gt", value: 29 };
    const filterB = { path: "$character.speed", op: "gt", value: 30 };

    const ruleAId = await createRule(apiRequest, charId, filterRule("gt-match", "HIT-gt", filterA));
    await createRule(apiRequest, charId, filterRule("gt-nomatch", "MISS-gt", filterB));

    const triggerResp = await apiRequest.post(`/characters/${charId}/homebrew/manual-trigger/${ruleAId}`);
    expect(triggerResp.ok(), `manual-trigger failed: ${triggerResp.status()}`).toBeTruthy();
    const body = await triggerResp.json();

    const msgs = notifMessages(body);
    expect(msgs.some(m => m.includes("HIT-gt")), `expected HIT-gt; got ${JSON.stringify(msgs)}`).toBeTruthy();
    expect(msgs.some(m => m.includes("MISS-gt")), `did not expect MISS-gt; got ${JSON.stringify(msgs)}`).toBeFalsy();
  });

  // 6. gte — greater than or equal
  test("gte operator matches when lhs >= rhs", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "gte" });

    // speed is 30; 30 >= 30 is true; 30 >= 31 is false
    const filterA = { path: "$character.speed", op: "gte", value: 30 };
    const filterB = { path: "$character.speed", op: "gte", value: 31 };

    const ruleAId = await createRule(apiRequest, charId, filterRule("gte-match", "HIT-gte", filterA));
    await createRule(apiRequest, charId, filterRule("gte-nomatch", "MISS-gte", filterB));

    const triggerResp = await apiRequest.post(`/characters/${charId}/homebrew/manual-trigger/${ruleAId}`);
    expect(triggerResp.ok(), `manual-trigger failed: ${triggerResp.status()}`).toBeTruthy();
    const body = await triggerResp.json();

    const msgs = notifMessages(body);
    expect(msgs.some(m => m.includes("HIT-gte")), `expected HIT-gte; got ${JSON.stringify(msgs)}`).toBeTruthy();
    expect(msgs.some(m => m.includes("MISS-gte")), `did not expect MISS-gte; got ${JSON.stringify(msgs)}`).toBeFalsy();
  });

  // 7. in — membership in list
  test("in operator matches when lhs in list", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "in" });

    // speed is 30; 30 in [30, 40] is true; 30 in [40, 50] is false
    const filterA = { path: "$character.speed", op: "in", value: [30, 40] };
    const filterB = { path: "$character.speed", op: "in", value: [40, 50] };

    const ruleAId = await createRule(apiRequest, charId, filterRule("in-match", "HIT-in", filterA));
    await createRule(apiRequest, charId, filterRule("in-nomatch", "MISS-in", filterB));

    const triggerResp = await apiRequest.post(`/characters/${charId}/homebrew/manual-trigger/${ruleAId}`);
    expect(triggerResp.ok(), `manual-trigger failed: ${triggerResp.status()}`).toBeTruthy();
    const body = await triggerResp.json();

    const msgs = notifMessages(body);
    expect(msgs.some(m => m.includes("HIT-in")), `expected HIT-in; got ${JSON.stringify(msgs)}`).toBeTruthy();
    expect(msgs.some(m => m.includes("MISS-in")), `did not expect MISS-in; got ${JSON.stringify(msgs)}`).toBeFalsy();
  });

  // 8. has_property — property existence check on item
  test("has_property operator matches when key exists in item metadata", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "has_property" });

    // Create a weapon with item_metadata carrying hb_foo
    const weaponResp = await apiRequest.post(`/characters/${charId}/items`, {
      data: {
        name: "PropWeapon",
        item_type: "weapon",
        quantity: 1,
        is_equipped: false,
        item_metadata: { hb_foo: "present" },
      },
    });
    expect(weaponResp.status(), `POST /items failed: ${weaponResp.status()}`).toBe(201);

    // Rule A: has_property "foo" (key exists) → MATCH
    // Rule B: has_property "bar" (key does not exist) → NOMATCH
    const filterA = { path: "$subject", op: "has_property", value: "foo" };
    const filterB = { path: "$subject", op: "has_property", value: "bar" };

    const itemSubject = { type: "item", filter: { item_types: ["weapon"] } };

    const ruleAId = await createRule(
      apiRequest,
      charId,
      filterRule("has_property-match", "HIT-has_property", filterA, itemSubject)
    );
    await createRule(
      apiRequest,
      charId,
      filterRule("has_property-nomatch", "MISS-has_property", filterB, itemSubject)
    );

    const triggerResp = await apiRequest.post(`/characters/${charId}/homebrew/manual-trigger/${ruleAId}`);
    expect(triggerResp.ok(), `manual-trigger failed: ${triggerResp.status()}`).toBeTruthy();
    const body = await triggerResp.json();

    const msgs = notifMessages(body);
    expect(msgs.some(m => m.includes("HIT-has_property")), `expected HIT-has_property; got ${JSON.stringify(msgs)}`).toBeTruthy();
    expect(msgs.some(m => m.includes("MISS-has_property")), `did not expect MISS-has_property; got ${JSON.stringify(msgs)}`).toBeFalsy();
  });

});
