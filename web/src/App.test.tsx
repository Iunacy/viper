// @vitest-environment jsdom
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { afterEach, describe, it, expect, vi } from "vitest";
import { Header, useClock } from "./App";
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
function ClockProbe() {
  const c = useClock(10);
  return (
    <>
      <output>{c.time.toFixed(2)}</output>
      <button onClick={c.toggle}>{c.playing ? "Pause" : "Play"}</button>
      <button onClick={() => c.setTime(10)}>End</button>
      <select
        aria-label="Speed"
        value={c.speed}
        onChange={(e) => c.setSpeed(Number(e.target.value))}
      >
        <option value={1}>1</option>
        <option value={2}>2</option>
      </select>
    </>
  );
}
describe("workspace controls", () => {
  it("identifies the active route and preserves real navigation destinations", () => {
    render(<Header route="/lab" />);
    expect(
      screen
        .getByRole("link", { name: "Laboratory" })
        .getAttribute("aria-current"),
    ).toBe("page");
    expect(
      screen.getByRole("link", { name: /GitHub/ }).getAttribute("href"),
    ).toBe("https://github.com/Iunacy/viper");
  });
  it("plays, pauses, changes speed and restarts at the end", () => {
    let callback: FrameRequestCallback = () => {};
    vi.stubGlobal(
      "requestAnimationFrame",
      vi.fn((cb) => {
        callback = cb;
        return 1;
      }),
    );
    vi.stubGlobal("cancelAnimationFrame", vi.fn());
    vi.spyOn(performance, "now").mockReturnValue(0);
    render(<ClockProbe />);
    fireEvent.click(screen.getByText("Play"));
    act(() => callback(1000));
    expect(screen.getByRole("status").textContent).toBe("1.00");
    fireEvent.click(screen.getByText("Pause"));
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "2" } });
    fireEvent.click(screen.getByText("Play"));
    act(() => callback(1000));
    expect(screen.getByRole("status").textContent).toBe("3.00");
    fireEvent.click(screen.getByText("End"));
    expect(screen.getByText("Play")).toBeTruthy();
    fireEvent.click(screen.getByText("Play"));
    expect(screen.getByRole("status").textContent).toBe("0.00");
  });
});
