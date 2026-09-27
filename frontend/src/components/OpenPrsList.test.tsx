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

    render(<OpenPrsList onReview={onReview} />);

    await user.type(screen.getByLabelText("Repository"), "octocat/Hello-World");
    await user.click(screen.getByRole("button", { name: "List open PRs" }));

    const link = await screen.findByRole("link", { name: "#12" });
    expect(link).toHaveAttribute("href", "https://github.com/octocat/Hello-World/pull/12");

    await user.click(screen.getByRole("button", { name: "Review" }));
    expect(onReview).toHaveBeenCalledWith("octocat/Hello-World", 12);
  });

  it("rejects an invalid repo format without calling the API", async () => {
    const listOpenPrs = vi.spyOn(client, "listOpenPrs");
    const user = userEvent.setup();

    render(<OpenPrsList onReview={vi.fn()} />);

    await user.type(screen.getByLabelText("Repository"), "not-a-valid-repo");
    await user.click(screen.getByRole("button", { name: "List open PRs" }));

    expect(listOpenPrs).not.toHaveBeenCalled();
    expect(screen.getByText("Couldn't load open PRs")).toBeInTheDocument();
    expect(screen.getByText("Expected 'owner/repo'.")).toBeInTheDocument();
  });

  it("shows a network-error message when the request itself fails to reach the server", async () => {
    vi.spyOn(client, "listOpenPrs").mockRejectedValue(new client.NetworkError());
    const user = userEvent.setup();

    render(<OpenPrsList onReview={vi.fn()} />);

    await user.type(screen.getByLabelText("Repository"), "octocat/Hello-World");
    await user.click(screen.getByRole("button", { name: "List open PRs" }));

    expect(
      await screen.findByText(
        "Can't reach the server. It may be waking up, try again in a moment.",
      ),
    ).toBeInTheDocument();
  });
});
