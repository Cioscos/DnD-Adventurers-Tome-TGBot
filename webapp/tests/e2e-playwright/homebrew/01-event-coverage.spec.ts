/**
 * 01-event-coverage.spec.ts
 *
 * 15 tests — one per event type supported by the homebrew rules engine.
 * Each test creates a character-subject notify rule, triggers the event via
 * the real API endpoint, and asserts the notification surfaces in the response.
 *
 * Notification field per endpoint:
 *   - Most endpoints  → response.homebrew_notifications
 *   - POST /homebrew/turn-start          → response.notifications
 *   - POST /homebrew/manual-trigger/{id} → response.notifications
 */

import { test, expect } from "./fixtures";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Build a minimal character-subject notify rule body. */
function notifyRule(event: string, message: string, name: string) {
  return {
    name,
    description: "Audit event-coverage rule",
    enabled: true,
    dsl: {
      version: 1,
      subject: { type: "character" },
      triggers: [
        { event, filters: [], effects: [{ action: "notify", severity: "info", message }] },
      ],
    },
  };
}

/** Assert that at least one notification contains the expected message. */
function assertFired(
  notifs: any[] | undefined | null,
  msg: string,
  field = "homebrew_notifications",
) {
  expect(Array.isArray(notifs), `${field} must be an array, got: ${JSON.stringify(notifs)}`).toBeTruthy();
  if (!Array.isArray(notifs)) return; // type-narrow; the first expect already failed
  expect(
    notifs.some((n) => typeof n.message === "string" && n.message.includes(msg)),
    `Expected a notification containing "${msg}" but got: ${JSON.stringify(notifs)}`
  ).toBeTruthy();
}

// ---------------------------------------------------------------------------
// Suite
// ---------------------------------------------------------------------------

test.describe("01-event-coverage", () => {

  // 1. attack_rolled
  test("attack_rolled fires on weapon attack", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "attack_rolled" });

    // Create an equipped weapon
    const addItemResp = await apiRequest.post(`/characters/${charId}/items`, {
      data: {
        name: "AuditBlade",
        item_type: "weapon",
        quantity: 1,
        is_equipped: true,
        item_metadata: { damage_dice: "1d8", weapon_type: "melee" },
      },
    });
    expect(addItemResp.status(), `POST /items failed: ${addItemResp.status()}`).toBe(201);
    const charBody = await addItemResp.json();
    const item = (charBody.items as any[]).find((i: any) => i.name === "AuditBlade");
    expect(item, "AuditBlade not found in items list").toBeTruthy();
    const itemId = item.id;

    // Install notify rule
    const ruleMsg = "event-attack_rolled-fired";
    const ruleResp = await apiRequest.post(`/characters/${charId}/homebrew/rules`, {
      data: notifyRule("attack_rolled", ruleMsg, "Audit attack_rolled"),
    });
    expect(ruleResp.status(), `POST /homebrew/rules failed: ${ruleResp.status()}`).toBe(201);

    // Trigger attack
    const attackResp = await apiRequest.post(`/characters/${charId}/items/${itemId}/attack`);
    expect(attackResp.status(), `POST /attack failed: ${attackResp.status()}`).toBe(200);
    const body = await attackResp.json();

    assertFired(body.homebrew_notifications, ruleMsg);
  });

  // 2. damage_taken
  test("damage_taken fires on hp damage op", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "damage_taken" });

    // NOTE: set_max / set_current ops hit a server-side 500 (missing flush before
    // build_character_response — see CONCERNS section). Use a character at 0 HP
    // instead; damage_taken fires on ANY damage event regardless of starting HP.

    // Install notify rule
    const ruleMsg = "event-damage_taken-fired";
    const ruleResp = await apiRequest.post(`/characters/${charId}/homebrew/rules`, {
      data: notifyRule("damage_taken", ruleMsg, "Audit damage_taken"),
    });
    expect(ruleResp.status(), `POST /homebrew/rules failed: ${ruleResp.status()}`).toBe(201);

    // Trigger damage — fires even on a 0-HP character
    const dmgResp = await apiRequest.patch(`/characters/${charId}/hp`, {
      data: { op: "damage", value: 5 },
    });
    expect(dmgResp.ok(), `damage op failed: ${dmgResp.status()}`).toBeTruthy();
    const body = await dmgResp.json();

    assertFired(body.homebrew_notifications, ruleMsg);
  });

  // 3. dropped_to_zero
  test("dropped_to_zero fires when HP crosses 0", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "dropped_to_zero" });

    // NOTE: set_max / set_current ops hit a server-side 500 (missing flush — see CONCERNS).
    // Use POST /classes to auto-bootstrap HP instead; a fighter level 1 starts with 10 HP.
    const classResp = await apiRequest.post(`/characters/${charId}/classes`, {
      data: { class_name: "fighter", level: 1, hit_die: 10 },
    });
    expect(classResp.status(), `POST /classes (HP bootstrap) failed: ${classResp.status()}`).toBe(201);

    // Install notify rule
    const ruleMsg = "event-dropped_to_zero-fired";
    const ruleResp = await apiRequest.post(`/characters/${charId}/homebrew/rules`, {
      data: notifyRule("dropped_to_zero", ruleMsg, "Audit dropped_to_zero"),
    });
    expect(ruleResp.status(), `POST /homebrew/rules failed: ${ruleResp.status()}`).toBe(201);

    // Trigger lethal damage (100 >> fighter's 10 HP)
    const dmgResp = await apiRequest.patch(`/characters/${charId}/hp`, {
      data: { op: "damage", value: 100 },
    });
    expect(dmgResp.ok(), `damage op failed: ${dmgResp.status()}`).toBeTruthy();
    const body = await dmgResp.json();

    assertFired(body.homebrew_notifications, ruleMsg);
  });

  // 4. hp_healed
  test("hp_healed fires on heal op", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "hp_healed" });

    // NOTE: set_max / set_current hit a server-side 500 (missing flush — see CONCERNS).
    // Use POST /classes to bootstrap HP, then damage the character so current < max,
    // then heal to trigger hp_healed.
    const classResp = await apiRequest.post(`/characters/${charId}/classes`, {
      data: { class_name: "fighter", level: 1, hit_die: 10 },
    });
    expect(classResp.status(), `POST /classes (HP bootstrap) failed: ${classResp.status()}`).toBe(201);

    // Damage first so current < max (3 damage, leaving 7/10)
    const dmgResp = await apiRequest.patch(`/characters/${charId}/hp`, {
      data: { op: "damage", value: 3 },
    });
    expect(dmgResp.ok(), `damage op failed: ${dmgResp.status()}`).toBeTruthy();

    // Install notify rule
    const ruleMsg = "event-hp_healed-fired";
    const ruleResp = await apiRequest.post(`/characters/${charId}/homebrew/rules`, {
      data: notifyRule("hp_healed", ruleMsg, "Audit hp_healed"),
    });
    expect(ruleResp.status(), `POST /homebrew/rules failed: ${ruleResp.status()}`).toBe(201);

    // Trigger heal
    const healResp = await apiRequest.patch(`/characters/${charId}/hp`, {
      data: { op: "heal", value: 2 },
    });
    expect(healResp.ok(), `heal op failed: ${healResp.status()}`).toBeTruthy();
    const body = await healResp.json();

    assertFired(body.homebrew_notifications, ruleMsg);
  });

  // 5. long_rest_taken
  test("long_rest_taken fires on long rest", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "long_rest_taken" });

    // Install notify rule
    const ruleMsg = "event-long_rest_taken-fired";
    const ruleResp = await apiRequest.post(`/characters/${charId}/homebrew/rules`, {
      data: notifyRule("long_rest_taken", ruleMsg, "Audit long_rest_taken"),
    });
    expect(ruleResp.status(), `POST /homebrew/rules failed: ${ruleResp.status()}`).toBe(201);

    // Trigger long rest
    const restResp = await apiRequest.post(`/characters/${charId}/rest`, {
      data: { rest_type: "long" },
    });
    expect(restResp.ok(), `long rest failed: ${restResp.status()}`).toBeTruthy();
    const body = await restResp.json();

    assertFired(body.homebrew_notifications, ruleMsg);
  });

  // 6. short_rest_taken
  test("short_rest_taken fires on short rest", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "short_rest_taken" });

    // Install notify rule
    const ruleMsg = "event-short_rest_taken-fired";
    const ruleResp = await apiRequest.post(`/characters/${charId}/homebrew/rules`, {
      data: notifyRule("short_rest_taken", ruleMsg, "Audit short_rest_taken"),
    });
    expect(ruleResp.status(), `POST /homebrew/rules failed: ${ruleResp.status()}`).toBe(201);

    // Trigger short rest
    const restResp = await apiRequest.post(`/characters/${charId}/rest`, {
      data: { rest_type: "short" },
    });
    expect(restResp.ok(), `short rest failed: ${restResp.status()}`).toBeTruthy();
    const body = await restResp.json();

    assertFired(body.homebrew_notifications, ruleMsg);
  });

  // 7. spell_cast
  test("spell_cast fires when spell slot used increases", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "spell_cast" });

    // Create a spell slot
    const slotResp = await apiRequest.post(`/characters/${charId}/spell_slots`, {
      data: { level: 1, total: 3, used: 0 },
    });
    expect(slotResp.status(), `POST /spell_slots failed: ${slotResp.status()}`).toBe(201);
    const slotBody = await slotResp.json();
    const slotId = slotBody.id;

    // Install notify rule
    const ruleMsg = "event-spell_cast-fired";
    const ruleResp = await apiRequest.post(`/characters/${charId}/homebrew/rules`, {
      data: notifyRule("spell_cast", ruleMsg, "Audit spell_cast"),
    });
    expect(ruleResp.status(), `POST /homebrew/rules failed: ${ruleResp.status()}`).toBe(201);

    // Trigger by incrementing used (0 → 1)
    const patchResp = await apiRequest.patch(`/characters/${charId}/spell_slots/${slotId}`, {
      data: { used: 1 },
    });
    expect(patchResp.ok(), `PATCH /spell_slots failed: ${patchResp.status()}`).toBeTruthy();
    const body = await patchResp.json();

    assertFired(body.homebrew_notifications, ruleMsg);
  });

  // 8. ability_used
  test("ability_used fires when ability uses decrements", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "ability_used" });

    // Create an ability with uses=3
    const abilityResp = await apiRequest.post(`/characters/${charId}/abilities`, {
      data: {
        name: "Audit Ability",
        description: "x",
        max_uses: 3,
        uses: 3,
        is_active: true,
        restoration_type: "short_rest",
      },
    });
    expect(abilityResp.status(), `POST /abilities failed: ${abilityResp.status()}`).toBe(201);
    const abilityBody = await abilityResp.json();
    const abilityId = abilityBody.id;

    // Install notify rule
    const ruleMsg = "event-ability_used-fired";
    const ruleResp = await apiRequest.post(`/characters/${charId}/homebrew/rules`, {
      data: notifyRule("ability_used", ruleMsg, "Audit ability_used"),
    });
    expect(ruleResp.status(), `POST /homebrew/rules failed: ${ruleResp.status()}`).toBe(201);

    // Trigger by decrementing uses (3 → 2)
    const patchResp = await apiRequest.patch(`/characters/${charId}/abilities/${abilityId}`, {
      data: { uses: 2 },
    });
    expect(patchResp.ok(), `PATCH /abilities failed: ${patchResp.status()}`).toBeTruthy();
    const body = await patchResp.json();

    assertFired(body.homebrew_notifications, ruleMsg);
  });

  // 9. item_equipped
  test("item_equipped fires when item becomes equipped", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "item_equipped" });

    // Create an unequipped ring (item_type must be "accessory" for ring slots)
    const addItemResp = await apiRequest.post(`/characters/${charId}/items`, {
      data: {
        name: "AuditRing",
        item_type: "accessory",
        quantity: 1,
        is_equipped: false,
      },
    });
    expect(addItemResp.status(), `POST /items failed: ${addItemResp.status()}`).toBe(201);
    const charBody = await addItemResp.json();
    const item = (charBody.items as any[]).find((i: any) => i.name === "AuditRing");
    expect(item, "AuditRing not found in items list").toBeTruthy();
    const itemId = item.id;

    // Install notify rule
    const ruleMsg = "event-item_equipped-fired";
    const ruleResp = await apiRequest.post(`/characters/${charId}/homebrew/rules`, {
      data: notifyRule("item_equipped", ruleMsg, "Audit item_equipped"),
    });
    expect(ruleResp.status(), `POST /homebrew/rules failed: ${ruleResp.status()}`).toBe(201);

    // Trigger by equipping the ring
    const patchResp = await apiRequest.patch(`/characters/${charId}/items/${itemId}`, {
      data: { is_equipped: true, equipment_slot: "ring1" },
    });
    expect(patchResp.ok(), `PATCH /items failed: ${patchResp.status()}`).toBeTruthy();
    const body = await patchResp.json();

    assertFired(body.homebrew_notifications, ruleMsg);
  });

  // 10. item_unequipped
  test("item_unequipped fires when item becomes unequipped", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "item_unequipped" });

    // Create an equipped ring (item_type must be "accessory" for ring slots)
    const addItemResp = await apiRequest.post(`/characters/${charId}/items`, {
      data: {
        name: "AuditRing2",
        item_type: "accessory",
        quantity: 1,
        is_equipped: true,
        equipment_slot: "ring1",
      },
    });
    expect(addItemResp.status(), `POST /items failed: ${addItemResp.status()}`).toBe(201);
    const charBody = await addItemResp.json();
    const item = (charBody.items as any[]).find((i: any) => i.name === "AuditRing2");
    expect(item, "AuditRing2 not found in items list").toBeTruthy();
    const itemId = item.id;

    // Install notify rule
    const ruleMsg = "event-item_unequipped-fired";
    const ruleResp = await apiRequest.post(`/characters/${charId}/homebrew/rules`, {
      data: notifyRule("item_unequipped", ruleMsg, "Audit item_unequipped"),
    });
    expect(ruleResp.status(), `POST /homebrew/rules failed: ${ruleResp.status()}`).toBe(201);

    // Trigger by unequipping
    const patchResp = await apiRequest.patch(`/characters/${charId}/items/${itemId}`, {
      data: { is_equipped: false },
    });
    expect(patchResp.ok(), `PATCH /items failed: ${patchResp.status()}`).toBeTruthy();
    const body = await patchResp.json();

    assertFired(body.homebrew_notifications, ruleMsg);
  });

  // 11. level_up
  test("level_up fires when class level increases", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "level_up" });

    // Create a class at level 1
    const classResp = await apiRequest.post(`/characters/${charId}/classes`, {
      data: { class_name: "fighter", level: 1, hit_die: 10 },
    });
    expect(classResp.status(), `POST /classes failed: ${classResp.status()}`).toBe(201);
    const classBody = await classResp.json();
    const cls = (classBody.classes as any[]).find((c: any) => c.class_name === "fighter");
    expect(cls, "fighter class not found in classes list").toBeTruthy();
    const classId = cls.id;

    // Install notify rule
    const ruleMsg = "event-level_up-fired";
    const ruleResp = await apiRequest.post(`/characters/${charId}/homebrew/rules`, {
      data: notifyRule("level_up", ruleMsg, "Audit level_up"),
    });
    expect(ruleResp.status(), `POST /homebrew/rules failed: ${ruleResp.status()}`).toBe(201);

    // Trigger by increasing level from 1 to 2
    const patchResp = await apiRequest.patch(`/characters/${charId}/classes/${classId}`, {
      data: { level: 2 },
    });
    expect(patchResp.ok(), `PATCH /classes failed: ${patchResp.status()}`).toBeTruthy();
    const body = await patchResp.json();

    assertFired(body.homebrew_notifications, ruleMsg);
  });

  // 12. resource_changed
  test("resource_changed fires when homebrew resource current changes", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "resource_changed" });

    // Create a rule that declares the resource AND triggers on resource_changed
    const ruleMsg = "event-resource_changed-fired";
    const ruleResp = await apiRequest.post(`/characters/${charId}/homebrew/rules`, {
      data: {
        name: "Audit Resource Changed",
        description: "x",
        enabled: true,
        dsl: {
          version: 1,
          subject: { type: "character" },
          resources: [{ key: "audit_res", name: "Audit Res", max: 3, restoration_type: "none" }],
          triggers: [
            {
              event: "resource_changed",
              filters: [],
              effects: [{ action: "notify", severity: "info", message: ruleMsg }],
            },
          ],
        },
      },
    });
    expect(ruleResp.status(), `POST /homebrew/rules failed: ${ruleResp.status()}`).toBe(201);

    // Find the materialized resource
    const resListResp = await apiRequest.get(`/characters/${charId}/homebrew/resources`);
    expect(resListResp.ok(), `GET /homebrew/resources failed: ${resListResp.status()}`).toBeTruthy();
    const resources = await resListResp.json();
    const resource = (resources as any[]).find((r: any) => r.key === "audit_res");
    expect(resource, "audit_res resource not found").toBeTruthy();
    const resId = resource.id;

    // Trigger by changing current (3 → 2)
    const patchResp = await apiRequest.patch(`/characters/${charId}/homebrew/resources/${resId}`, {
      data: { current: 2 },
    });
    expect(patchResp.ok(), `PATCH /homebrew/resources failed: ${patchResp.status()}`).toBeTruthy();
    const body = await patchResp.json();

    assertFired(body.homebrew_notifications, ruleMsg);
  });

  // 13. resource_depleted
  test("resource_depleted fires when homebrew resource current hits 0", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "resource_depleted" });

    // Create a rule that declares the resource AND triggers on resource_depleted
    const ruleMsg = "event-resource_depleted-fired";
    const ruleResp = await apiRequest.post(`/characters/${charId}/homebrew/rules`, {
      data: {
        name: "Audit Resource Depleted",
        description: "x",
        enabled: true,
        dsl: {
          version: 1,
          subject: { type: "character" },
          resources: [{ key: "audit_res2", name: "Audit Res 2", max: 3, restoration_type: "none" }],
          triggers: [
            {
              event: "resource_depleted",
              filters: [],
              effects: [{ action: "notify", severity: "info", message: ruleMsg }],
            },
          ],
        },
      },
    });
    expect(ruleResp.status(), `POST /homebrew/rules failed: ${ruleResp.status()}`).toBe(201);

    // Find the materialized resource
    const resListResp = await apiRequest.get(`/characters/${charId}/homebrew/resources`);
    expect(resListResp.ok(), `GET /homebrew/resources failed: ${resListResp.status()}`).toBeTruthy();
    const resources = await resListResp.json();
    const resource = (resources as any[]).find((r: any) => r.key === "audit_res2");
    expect(resource, "audit_res2 resource not found").toBeTruthy();
    const resId = resource.id;

    // Trigger by depleting (3 → 0)
    const patchResp = await apiRequest.patch(`/characters/${charId}/homebrew/resources/${resId}`, {
      data: { current: 0 },
    });
    expect(patchResp.ok(), `PATCH /homebrew/resources failed: ${patchResp.status()}`).toBeTruthy();
    const body = await patchResp.json();

    assertFired(body.homebrew_notifications, ruleMsg);
  });

  // 14. turn_started
  test("turn_started fires on turn-start endpoint", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "turn_started" });

    // Install notify rule
    const ruleMsg = "event-turn_started-fired";
    const ruleResp = await apiRequest.post(`/characters/${charId}/homebrew/rules`, {
      data: notifyRule("turn_started", ruleMsg, "Audit turn_started"),
    });
    expect(ruleResp.status(), `POST /homebrew/rules failed: ${ruleResp.status()}`).toBe(201);

    // Trigger via turn-start endpoint
    const turnResp = await apiRequest.post(`/characters/${charId}/homebrew/turn-start`);
    expect(turnResp.ok(), `POST /homebrew/turn-start failed: ${turnResp.status()}`).toBeTruthy();
    const body = await turnResp.json();

    // turn-start returns { notifications: [...] }
    assertFired(body.notifications, ruleMsg, "notifications");
  });

  // 15. manual_trigger
  test("manual_trigger fires on manual-trigger endpoint", async ({ apiRequest, charId }) => {
    test.info().annotations.push({ type: "event", description: "manual_trigger" });

    // Install notify rule and capture its ID
    const ruleMsg = "event-manual_trigger-fired";
    const ruleResp = await apiRequest.post(`/characters/${charId}/homebrew/rules`, {
      data: notifyRule("manual_trigger", ruleMsg, "Audit manual_trigger"),
    });
    expect(ruleResp.status(), `POST /homebrew/rules failed: ${ruleResp.status()}`).toBe(201);
    const ruleBody = await ruleResp.json();
    const ruleId = ruleBody.id;

    // Trigger via manual-trigger endpoint
    const triggerResp = await apiRequest.post(`/characters/${charId}/homebrew/manual-trigger/${ruleId}`);
    expect(triggerResp.ok(), `POST /homebrew/manual-trigger failed: ${triggerResp.status()}`).toBeTruthy();
    const body = await triggerResp.json();

    // manual-trigger returns { notifications: [...] }
    assertFired(body.notifications, ruleMsg, "notifications");
  });

});
