import { test as base, APIRequestContext, expect } from "@playwright/test";

export type HomebrewFixture = {
  apiRequest: APIRequestContext;
  charId: number;
  installTemplate(templateId: string): Promise<number>;
  resetCharacter(): Promise<void>;
};

export const test = base.extend<HomebrewFixture>({
  apiRequest: async ({ playwright }, use) => {
    const ctx = await playwright.request.newContext({
      baseURL: process.env.HB_API_URL ?? "http://127.0.0.1:8000",
      extraHTTPHeaders: { "X-Telegram-Init-Data": "DEV_USER_FALLBACK" },
    });
    await use(ctx);
    await ctx.dispose();
  },

  charId: async ({ apiRequest }, use) => {
    const resp = await apiRequest.post("/characters", {
      data: { name: `HBFixture-${Date.now()}` },
    });
    expect(resp.ok(), `POST /characters failed: ${resp.status()}`).toBeTruthy();
    const body = await resp.json();
    await use(body.id);
    await apiRequest.delete(`/characters/${body.id}`);
  },

  installTemplate: async ({ apiRequest, charId }, use) => {
    const fn = async (templateId: string) => {
      const r = await apiRequest.post(
        `/characters/${charId}/homebrew/templates/${templateId}/install`
      );
      expect(r.ok(), `install template failed: ${r.status()}`).toBeTruthy();
      return (await r.json()).id;
    };
    await use(fn);
  },

  resetCharacter: async ({ apiRequest, charId }, use) => {
    const fn = async () => {
      const resp = await apiRequest.get(
        `/characters/${charId}/homebrew/rules`
      );
      const rules = await resp.json();
      for (const rule of rules) {
        await apiRequest.delete(
          `/characters/${charId}/homebrew/rules/${rule.id}`
        );
      }
    };
    await use(fn);
  },
});

export { expect } from "@playwright/test";
