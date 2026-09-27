import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ErrorBox } from "./ErrorBox";

describe("ErrorBox", () => {
  it("renders both the title and the message", () => {
    render(<ErrorBox title="Review failed" message="PR #7 does not exist in owner/repo." />);

    expect(screen.getByText("Review failed")).toBeInTheDocument();
    expect(screen.getByText("PR #7 does not exist in owner/repo.")).toBeInTheDocument();
  });
});
