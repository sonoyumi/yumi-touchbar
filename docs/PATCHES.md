# Patches to touchbard

Both patches apply to [0800tim/touchbard](https://github.com/0800tim/touchbard) at commit
`1b29141c2a592b81c14f05b8590c34ce78bb99cf`; `install.sh` checks out exactly that commit before applying them.

## 0001 - daemon (`daemon/src`, Rust; one line in `system/install.sh`)

| Change | Why |
|---|---|
| **Long swipe between layers.** `swipe_layers` (2-5 layers) form a ring; the layer follows the finger, the neighbour slides in from the edge with its name, and an indicator "Name ● ○ ○" shows where you are. Settings: `swipe_min`, `swipe_start`, `swipe_anim_ms`, `layer_names`. | touchbard switches layers only with buttons; five layers of tools need a gesture. |
| **Two-finger swipe from anywhere.** A second finger cancels what the first one started (releases the key, closes the slider and restores its value) and drives the swipe by the mean of both fingers. | With one finger a swipe cannot start on a slider or on media keys. |
| **Deferred key presses on swipe layers** (`KEY_DEFER` 350 ms): a key button is pressed on release or after 350 ms of holding. | A swipe that started on ⏯ used to pause the music before the swipe was recognised. Taps are not slower. |
| **App layer joins the ring** in front of the main layer instead of replacing it. | Otherwise, after leaving an app layer with the "main" button, the main layer was outside the ring and could not be swiped. |
| **Cyrillic in the built-in 5x7 font.** | Layer names and labels in Russian/Ukrainian were drawn as boxes. |
| Preview options `swipe=` and `anim=` for `touchbard --preview`. | Designing the swipe without hardware. |
| **Outline pills and a serif font** (`theme.pill_style = "outline"`, `theme.font = "Noto Serif, JetBrainsMono Nerd Font"`): buttons are drawn as 1 px frames, captions such as 天気 / 音楽 sit under a small icon. | The bar matches the "ink" style of the desktop and lock screen. |
| **Touch ID window "seal"** (`touchid_style = "seal"`, `touchid_seal = …png`): the fingerprint prompt shows the seal image and stays until fprintd stops waiting for a finger. `system/install.sh` installs `share/touchbar/hanko.png`. | The old prompt vanished on a timer while the sensor was still waiting. Works with [yumi-touchid](https://github.com/sonoyumi/yumi-touchid). |
| **Frame cap** `fps` (default 30) and an optional frame counter in the log (`fps_log`); the frame buffer is mapped once instead of on every frame. | Less CPU while the equaliser and the cat are moving. |
| A swiped layer is drawn without press highlights; the "Name ● ○ ○" badge after a swipe. | No flashes of buttons that were not pressed. |
| Smaller things: no "Karaoke mode on/off" toast, a "lines of text" icon for the lyrics button, a touch on the player closes the lyrics offset panel without pausing. | Less noise on a 60 px bar. |

13 unit tests in `ui.rs` (upstream had none): the swipe ring, two fingers, deferred keys, the app layer in the ring, and "old gestures still work" - sliders, weather scrolling, plain key presses without a ring.

## 0002 - session agent (`agent/touchbar-agent`, Python)

| Change | Why |
|---|---|
| `apps_fullscreen_only` setting. | App layers either for any focused window or only fullscreen ones. |
| Hidden plugins are kept alive 120 s instead of 10 s. | Swiping through layers restarted plugins and they faded in again every time. |
| 12-day forecast for swiping in the expanded weather; last known weather shown at once after boot, retried every 10 s until the network is up. | No empty weather at boot. |
| Lyrics from the yumi-rice player (yumilyrics) first, LRCLIB as before as the fallback. | LRCLIB alone rate-limited and missed songs the desktop player had. Without yumi-rice it is plain LRCLIB. |
| Every 2 s the sound/mic buttons are re-checked against PipeWire. | A lost pactl event left Mute on the bar out of sync with the system. |
| Reconnect to the daemon after 0.2 s instead of 2 s; swipe layer changes are logged. | Less of the stale layout at start; easy to debug gestures. |
| Buttons of the built-in presets call yumi-rice commands instead of Omarchy ones (`apps`, `menu`, `screenshot`, `lock`); Omarchy-only presets (overview, record, night light) are removed. | The bar runs on yumi-rice, not on Omarchy. |
| Settings passed through: `swipe_*`, `layer_names`, `fps`, `fps_log`, `touchid_style`, `touchid_seal`, `pill_style`. | So the style file can set them. |
| The Touch ID window is closed by the agent when fprintd stops waiting (also when the lock screen cancels the check). | No prompt left hanging after unlocking with the password. |

## 0003 - plugin start (`agent/touchbar-agent`, Python)

| Change | Why |
|---|---|
| A `.py` plugin without the exec bit is started with `python3 plugin.py` instead of failing. | A rewritten `plugin.py` lost its exec bit, the agent got "Permission denied" on every frame and the bar showed an empty grey cell. |
