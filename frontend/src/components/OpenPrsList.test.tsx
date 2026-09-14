import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { OpenPrsList } from "./OpenPrsList";
import * as client from "../api/client";

describe("OpenPrsList", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("links each row to the PR on GitHub and calls onReview with repo + number", async () => {
    vi.spyOn(client, "listOpenPrs").mockResolvedValue([
      { number: 12, title: "Add dark mode", author: "alice", age_days: 3 },
    ]);
    const onReview = vi.fn();
    const user = userEvent.setup();

    render(<OpenPrsList apiKey="k" onReview={onReview} />);

    await user.type(screen.getByLabelText("Repository"), "octocat/Hello-World");
    await user.click(screen.getByRole("button", { name: "List open PRs" }));

    const link = await screen.findByRole("link", { name: "#12" });
    expect(link).toHaveAttribute("href", "https://github.com/octocat/Hello-World/pull/12");

    await user.click(screen.getByRole("button", { name: "Review" }));
    expect(onReview).toHaveBeenCalledWith("octocat/Hello-World", 12);
  });
});
