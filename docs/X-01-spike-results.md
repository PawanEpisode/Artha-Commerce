# X-01 spike results

Written results of the device spikes for X-01. Each section says who ran it, on what, and the go or no-go.

## P4 spikes (pop-out), runbook W4.0

Criteria are in `docs/X-01-ROLLOUT.md`, section 6, W4.0. Run the throwaway page (`spike-p4.local`, not committed), press
"Copy results" and paste its output under a dated heading below, one per browser and OS. Add screenshots for S4.5 beside this
file or link them.

### Go or no-go summary (fill in last)

| Spike | Chrome (macOS) | Edge | Firefox 151+ | Safari (macOS) | Decision |
| --- | --- | --- | --- | --- | --- |
| S4.1 Availability, portal, resize | Pass with a finding: minimum window is 320x156 inner; clicks and keys reach a React portal; `resizeTo` untested above the minimum | not run | not run | n/a (no API) | Go. Sizes become Compact 320x156 and Card 320x300; the layout adapts to the window |
| S4.2 Open from Start | Pass: opens from click and Space (about 390 ms); fails after 8 s (NotAllowedError) | not run | not run | n/a | Go. `open()` is called first in the Start handler |
| S4.3 Background throttling | Dry run 2 min passed (tick gap 1002 ms, heartbeat gap 20002 ms), window visible; 15 min hidden run not done | not run | not run | n/a | Go, verify the 15 min hidden run on the W4.2 build |
| S4.4 Wake lock in the pop-out | Main tab lock was released when the tab was hidden (screen locked); lock from the pop-out not tested | not run | not run | n/a | Build it (request from the pop-out document); verify on the W4.2 build |
| S4.5 Theming | Pass: clone works, no difference to inline, Nunito loads, theme follows in 7 ms, 20/20 contrast checks pass (stand-in colours); four screenshots taken | not run | not run | not run | Go. Clone with absolute `href`, inline fallback |
| S4.6 Back to the opener | Pass: `window.focus()` brought the hidden tab forward | not run | not run | n/a | Go. "Back to Artha" is shown |
| S4.7 Safari video trick | Frozen at 00:00 (harness timer had expired, not conclusive); `window.open` opened a tab, not a window | n/a | not run | Clock updated while switching tabs and apps; `window.open` gave a small separate window that updated | Go for Safari, backlog (not in P4). W4.4 uses `window.open` |

Not tested: Edge, Firefox 151+, Windows, second monitor, reduced motion in the window, `resizeTo` above the minimum, S4.4 in the pop-out. The 15 minute hidden run and the wake lock in the pop-out are verified in the W4.2 device checks. Decisions taken on 2026-10-07 (owner): Compact and Card sizes, toggle tries `resizeTo` and otherwise changes the layout only, open spikes are verified on the W4.2 build, Safari video trick goes to the backlog.

### Runs

Markdown after testing :-

### P4 spikes (2026-10-07 11:25)

Environment:
- Browser (user agent): Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36
- Platform: macOS
- Secure context: true
- documentPictureInPicture: yes
- wakeLock: yes
- setAppBadge: yes
- onbeforeinstallprompt: yes
- Video PiP (requestPictureInPicture): yes
- Display mode standalone: false
- Reduced motion (this page): true
- Screen: 1920x1080 @1x

| Spike | Result | Notes and measurements |
| --- | --- | --- |
| S4.1 | PASS | Asked 260x72, window reports inner 320x156 Plain window: clicks=3, keys=11 resizeTo from click (plain): 260x72 -> 320x156 (changed) React portal: clicks=3, key events=19, Enter=5 resizeTo from click (react): 320x156 -> 320x156 (NO CHANGE) resizeTo from the opener (no click in the window): 320x156 -> 320x156 |
| S4.2 | PARTIAL | click, open first: window opened (399 ms after the handler began) -> OK Space key, open first: window opened (387 ms after the handler began) -> OK Open after 8000 ms: FAILED NotAllowedError: Failed to execute 'requestWindow' on 'DocumentPictureInPicture': Document PiP requires user activation (expected once activation lapses) |
| S4.3 | PASS | Run 2 min (4:09:41 PM). Pop-out timers: 120 ticks, longest gap 1002 ms, 0 gaps over 1.5 s; heartbeats 5, longest gap 20002 ms (ok 12, failed 0). This tab's timers (comparison): 120 ticks, longest gap 1002 ms, 0 over 1.5 s; heartbeats 5, longest gap 20002 ms. Suggested verdict: PASS (pop-out tick gap <= 1500 ms and heartbeat gap <= 25000 ms). |
| S4.4 | not run | Step 3 - passed as no screen lock during the period Step 4 - tab infront - passed, tab hidden - screen got locked , lock got released / Lock requested from main at 4:36:28 PM: acquired Lock (main) RELEASED by the browser or by you after 6 s (main tab was hidden) |
| S4.5 | not run | For styles - clone links or inline CSS, the pill opened with same styles, no difference / Styles (inline): 1 links, 2 inline. Nunito loaded in the window: true. Clock font-family: Nunito, system-ui, sans-serif Last theme follow: 7 ms Contrast sweep (stand-in colours): 20/20 pass AA 4.5. Take the four screenshots by hand. |
| S4.6 | PASS | Back to opener: before visible=hidden focused=false; after visible=visible focused=true (tab took focus) |
| S4.7 | not run | Step 1 - In google chorme - reasbale clock is displaying but its 00:00, and not getting updated at all, it did not even started. Step 2 - A new tab opened in chrome instead of a small window, and the timer is not getting updated at all , if switching tabs. / Canvas video PiP started. Watch whether the clock keeps updating after you switch tabs and apps for a minute. Popup: inner 1920x958, outer 1920x958, toolbar visible=false, locationbar visible=false. Check by eye: is it a small window (not a tab), and does it keep updating while this tab is hidden? |


