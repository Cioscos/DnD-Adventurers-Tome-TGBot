/**
 * 04-passive-modifiers.spec.ts
 *
 * 5 tests — one per passive modifier field exposed by the homebrew rules engine.
 * Passive modifiers have NO triggers — they have a passive_modifiers array.
 * Each modifier has when/target/value/label_i18n.
 *
 * The server evaluates them when building the character response and exposes
 * them in dedicated fields:
 *   - AC: character.ac_breakdown.homebrew
 *   - HP max: character.hp_max_homebrew_modifier
 *   - Speed: character.speed_homebrew_modifier
 *   - Skills: character.skills_homebrew_modifiers
 *   - Saves: character.saves_homebrew_modifiers
 */

import { test, expect } from "./fixtures";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Build a passive-modifier rule body. */
function passiveRule(name: string, subject: any, target: string, value: number, when: any) {
  return {
    name,
    enabled: true,
    dsl: {
      version: 1,
      subject,
      passive_modifiers: [
        { when, target, value, label_i18n: { it: name, en: name } },
      ],
      triggers: [],
    },
  };
}

/** Tautological character filter: $character.id > 0 (always true). */
const ALWAYS_TRUE_CHAR = { path: "$character.id", op: "gt", value: 0 };

// ---------------------------------------------------------------------------
// Suite
// ---------------------------------------------------------------------------

test.describe("04-passive-modifiers", () => {

  // 1. AC breakdown includes homebrew shield bonus
  test("AC breakdown.homebrew reflects +1 from equipped shield rule", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "character.ac" });

    // Create rule: +1 AC for equipped shields
    const ruleBody = passiveRule(
      "+1 AC Shield",
      { type: "item", filter: { item_types: ["shield"] } },
      "character.ac",
      1,
      { path: "$subject.is_equipped", op: "eq", value: true },
    );
    const ruleResp = await apiRequest.post(`/characters/${charId}/homebrew/rules`, {
      data: ruleBody,
    });
    expect(ruleResp.status(), `POST /homebrew/rules failed: ${ruleResp.status()}`).toBe(201);

    // Create equipped shield
    const shieldResp = await apiRequest.post(`/characters/${charId}/items`, {
      data: { name: "Scudo", item_type: "shield", quantity: 1, is_equipped: true },
    });
    expect(shieldResp.status(), `POST /items failed: ${shieldResp.status()}`).toBe(201);

    // GET character
    const charResp = await apiRequest.get(`/characters/${charId}`);
    expect(charResp.status(), `GET /characters failed: ${charResp.status()}`).toBe(200);
    const char = await charResp.json();

    // Assert AC breakdown contains homebrew modifier
    expect(char.ac_breakdown, "ac_breakdown missing").toBeTruthy();
    expect(char.ac_breakdown.homebrew, "ac_breakdown.homebrew should be 1").toBe(1);
    expect(typeof char.ac_breakdown.base, "ac_breakdown.base should be int").toBe("number");
    expect(typeof char.ac_breakdown.shield, "ac_breakdown.shield should be int").toBe("number");
    expect(typeof char.ac_breakdown.magic, "ac_breakdown.magic should be int").toBe("number");
  });

  // 2. HP max homebrew modifier
  test("hp_max_homebrew_modifier reflects +5 from character-level rule", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "character.hit_points_max" });

    // Create rule: +5 HP
    const ruleBody = passiveRule(
      "+5 HP Bonus",
      { type: "character" },
      "character.hit_points_max",
      5,
      ALWAYS_TRUE_CHAR,
    );
    const ruleResp = await apiRequest.post(`/characters/${charId}/homebrew/rules`, {
      data: ruleBody,
    });
    expect(ruleResp.status(), `POST /homebrew/rules failed: ${ruleResp.status()}`).toBe(201);

    // GET character
    const charResp = await apiRequest.get(`/characters/${charId}`);
    expect(charResp.status(), `GET /characters failed: ${charResp.status()}`).toBe(200);
    const char = await charResp.json();

    // Assert HP max homebrew modifier
    expect(char.hp_max_homebrew_modifier, "hp_max_homebrew_modifier should be 5").toBe(5);
  });

  // 3. Speed homebrew modifier
  test("speed_homebrew_modifier reflects +5 from character.speed rule", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "character.speed" });

    // Create rule: +5 Speed
    const ruleBody = passiveRule(
      "+5 Speed",
      { type: "character" },
      "character.speed",
      5,
      ALWAYS_TRUE_CHAR,
    );
    const ruleResp = await apiRequest.post(`/characters/${charId}/homebrew/rules`, {
      data: ruleBody,
    });
    expect(ruleResp.status(), `POST /homebrew/rules failed: ${ruleResp.status()}`).toBe(201);

    // GET character
    const charResp = await apiRequest.get(`/characters/${charId}`);
    expect(charResp.status(), `GET /characters failed: ${charResp.status()}`).toBe(200);
    const char = await charResp.json();

    // Assert speed homebrew modifier
    expect(char.speed_homebrew_modifier, "speed_homebrew_modifier should be 5").toBe(5);
  });

  // 4. Skill stealth homebrew modifier
  test("skills_homebrew_modifiers contains only stealth=2", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "character.skill.stealth" });

    // Create rule: +2 Stealth
    const ruleBody = passiveRule(
      "+2 Stealth",
      { type: "character" },
      "character.skill.stealth",
      2,
      ALWAYS_TRUE_CHAR,
    );
    const ruleResp = await apiRequest.post(`/characters/${charId}/homebrew/rules`, {
      data: ruleBody,
    });
    expect(ruleResp.status(), `POST /homebrew/rules failed: ${ruleResp.status()}`).toBe(201);

    // GET character
    const charResp = await apiRequest.get(`/characters/${charId}`);
    expect(charResp.status(), `GET /characters failed: ${charResp.status()}`).toBe(200);
    const char = await charResp.json();

    // Assert skills homebrew modifiers — exact match, only stealth present
    expect(char.skills_homebrew_modifiers).toEqual({ stealth: 2 });
  });

  // 5. Save wisdom homebrew modifier
  test("saves_homebrew_modifiers contains only wisdom=3", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "character.saving_throw.wisdom" });

    // Create rule: +3 Wisdom Save (note: target is character.saving_throw.wisdom, not character.save.wisdom)
    const ruleBody = passiveRule(
      "+3 WIS Save",
      { type: "character" },
      "character.saving_throw.wisdom",
      3,
      ALWAYS_TRUE_CHAR,
    );
    const ruleResp = await apiRequest.post(`/characters/${charId}/homebrew/rules`, {
      data: ruleBody,
    });
    expect(ruleResp.status(), `POST /homebrew/rules failed: ${ruleResp.status()}`).toBe(201);

    // GET character
    const charResp = await apiRequest.get(`/characters/${charId}`);
    expect(charResp.status(), `GET /characters failed: ${charResp.status()}`).toBe(200);
    const char = await charResp.json();

    // Assert saves homebrew modifiers — exact match, only wisdom present
    expect(char.saves_homebrew_modifiers).toEqual({ wisdom: 3 });
  });

  // 6. AC breakdown homebrew is 0 when shield is unequipped (when filter gates)
  test("AC breakdown.homebrew is 0 when shield is unequipped", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "character.ac (unequipped)" });

    const ruleBody = passiveRule(
      "+1 AC Shield",
      { type: "item", filter: { item_types: ["shield"] } },
      "character.ac",
      1,
      { path: "$subject.is_equipped", op: "eq", value: true },
    );
    const r = await apiRequest.post(`/characters/${charId}/homebrew/rules`, { data: ruleBody });
    expect(r.status(), `rule create failed: ${r.status()}`).toBe(201);

    const item = await apiRequest.post(`/characters/${charId}/items`, {
      data: { name: "Scudo", item_type: "shield", quantity: 1, is_equipped: false },
    });
    expect(item.status(), `shield create failed: ${item.status()}`).toBe(201);

    const charResp = await apiRequest.get(`/characters/${charId}`);
    expect(charResp.status()).toBe(200);
    const char = await charResp.json();
    expect(char.ac_breakdown.homebrew, "homebrew AC must be 0 when shield unequipped").toBe(0);
  });

});
