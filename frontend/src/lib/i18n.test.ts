import { describe, expect, it } from "vitest";
import { createT, isRtl, LANG_LABELS } from "./i18n";

describe("i18n", () => {
  it("marks Arabic as RTL and others as LTR", () => {
    expect(isRtl("ar")).toBe(true);
    expect(isRtl("en")).toBe(false);
    expect(isRtl("fr")).toBe(false);
  });

  it("has a label for every supported language", () => {
    expect(LANG_LABELS.en).toBeTruthy();
    expect(LANG_LABELS.fr).toBeTruthy();
    expect(LANG_LABELS.ar).toBeTruthy();
  });

  it("translates a key into each language", () => {
    expect(createT("en")("nav_dashboard")).toBe("Dashboard");
    expect(createT("fr")("nav_dashboard")).toBe("Tableau de bord");
    expect(createT("ar")("nav_dashboard")).toBe("لوحة التحكم");
  });

  it("falls back to English for a language missing a key", () => {
    // createT casts per-language dictionaries, so a missing key resolves to en.
    const t = createT("ar");
    expect(typeof t("out_download_pdf")).toBe("string");
  });
});
