import { describe, it, expect } from "vitest";
import { cn } from "../utils";

describe("cn", () => {
  it("returns a single class unchanged", () => {
    expect(cn("text-red-500")).toBe("text-red-500");
  });

  it("merges multiple classes", () => {
    const result = cn("px-4", "py-2", "text-sm");
    expect(result).toContain("px-4");
    expect(result).toContain("py-2");
    expect(result).toContain("text-sm");
  });

  it("resolves tailwind conflicts — last wins", () => {
    // tailwind-merge: px-4 then px-6 → px-6 wins
    const result = cn("px-4", "px-6");
    expect(result).toBe("px-6");
  });

  it("ignores falsy values", () => {
    const result = cn("text-sm", false, undefined, null as unknown as string, "font-bold");
    expect(result).toContain("text-sm");
    expect(result).toContain("font-bold");
    expect(result).not.toContain("false");
  });

  it("handles conditional class objects", () => {
    const result = cn({ "text-red-500": true, "text-blue-500": false });
    expect(result).toContain("text-red-500");
    expect(result).not.toContain("text-blue-500");
  });

  it("returns empty string for no arguments", () => {
    expect(cn()).toBe("");
  });
});
