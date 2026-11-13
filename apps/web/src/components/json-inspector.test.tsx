import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { JsonInspector } from "./json-inspector";

it("supports expanding nested values and preserves JSON primitive types", () => {
  render(
    <JsonInspector
      value={{ nested: { answer: 42, ready: true }, missing: null }}
      label="input"
    />,
  );
  const nested = screen.getByText("nested").closest("details")!;
  expect(nested).not.toHaveAttribute("open");
  fireEvent.click(screen.getByText("nested"));
  expect(nested).toHaveAttribute("open");
  expect(screen.getByText("42")).toBeVisible();
  expect(screen.getByText("true")).toBeVisible();
  expect(screen.getByText("null")).toBeVisible();
});
