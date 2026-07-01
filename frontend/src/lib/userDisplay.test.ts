import { describe, it, expect } from "vitest";
import { getInitials, toDisplayUser } from "./userDisplay";
import type { User } from "@supabase/supabase-js";

describe("getInitials", () => {
  it("uses first and last initials for multi-word names", () => {
    expect(getInitials("Ada Lovelace")).toBe("AL");
    expect(getInitials("Jean Pierre Dupont")).toBe("JD");
  });

  it("uses the first two letters for a single name", () => {
    expect(getInitials("Cher")).toBe("CH");
  });

  it("collapses extra whitespace", () => {
    expect(getInitials("  Ada   Lovelace  ")).toBe("AL");
  });

  it("falls back to U for empty input", () => {
    expect(getInitials("   ")).toBe("U");
  });
});

describe("toDisplayUser", () => {
  it("prefers full_name from metadata", () => {
    const user = {
      email: "ada@test.com",
      user_metadata: { full_name: "Ada Lovelace" },
    } as unknown as User;
    expect(toDisplayUser(user)).toEqual({
      name: "Ada Lovelace",
      email: "ada@test.com",
    });
  });

  it("falls back to the email local-part when no name is present", () => {
    const user = {
      email: "ada@test.com",
      user_metadata: {},
    } as unknown as User;
    expect(toDisplayUser(user).name).toBe("ada");
  });
});
