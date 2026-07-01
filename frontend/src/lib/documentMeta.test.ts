import { describe, it, expect, beforeEach } from "vitest";
import {
  getDocumentMeta,
  setDocumentMeta,
  removeDocumentMeta,
  getDocumentMetaOrDefault,
} from "./documentMeta";

describe("documentMeta", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("returns null for an unknown document", () => {
    expect(getDocumentMeta("missing")).toBeNull();
  });

  it("stores and reads back metadata", () => {
    setDocumentMeta("doc1", { subject: "Math", tags: ["algebra"] });
    expect(getDocumentMeta("doc1")).toEqual({
      subject: "Math",
      tags: ["algebra"],
    });
  });

  it("removes metadata", () => {
    setDocumentMeta("doc1", { subject: "Math", tags: [] });
    removeDocumentMeta("doc1");
    expect(getDocumentMeta("doc1")).toBeNull();
  });

  it("returns the default when nothing is stored", () => {
    expect(getDocumentMetaOrDefault("doc1")).toEqual({
      subject: "General",
      tags: [],
    });
  });

  it("returns stored value over the default", () => {
    setDocumentMeta("doc1", { subject: "Physics", tags: ["motion"] });
    expect(getDocumentMetaOrDefault("doc1")).toEqual({
      subject: "Physics",
      tags: ["motion"],
    });
  });
});
