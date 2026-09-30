# NetBSD 11.0 ADJUSTED kernel validation

Validation date: 2026-09-30

Kernel under test:

```text
NetBSD 11.0 (build-ADJUSTED) #0
```

## Passed checks

- Kernel boots successfully from `/netbsd.adjusted`.
- GNOME/X11 starts and applications can be used.
- Intel i915 DRM initializes; `glxinfo -B` reports direct rendering and hardware acceleration on Intel HD Graphics 5500 (Broadwell GT2).
- Radeon DRM initializes far enough for display support; the pre-existing VCE resume warning remains unchanged from GENERIC.
- Ethernet `wm0` is active at 1000baseT full duplex.
- IPv4 connectivity works (1.1.1.1 reachable with 0% packet loss).
- DNS works (`www.netbsd.org` resolves and replies).
- Intel Wi-Fi `iwm0` is present; association was not tested in this run because Ethernet was in use.
- USB mass storage works: a Kanguru FlashBlu device attached through `umass0` / `sd0` and its partitions were detected.
- Realtek ALC280 (`audio1`) playback test completed on both channels.
- Realtek ALC280 remains selected as the default audio device after subsequent checks.
- X11 keyboard layout reports `se,us`, with Swedish first.
- Console wscons accepts `encoding sv`. NetBSD reports the resulting encoding symbolically as `fi` because KB_SV and KB_FI share encoding value 0x0900.
- ACPI battery reporting works: battery present, AC adapter connected, 97.31% charge reported.
- ACPI thermal and WMI sensors are visible through `envstat`.
- The machine firmware/ACPI advertises S0, S3, S4 and S5, but suspend/lid-triggered power management is intentionally not part of the target configuration. `acpibut*` and `acpilid*` are disabled in ADJUSTED; core ACPI, CPU power states, thermal zones, battery reporting and display support remain enabled.
- Kernel identity re-confirmed as `NetBSD 11.0 (build-ADJUSTED)`.

## Expected / pre-existing warnings

These were also observed with GENERIC and are not currently attributed to the adjusted kernel:

- `sdmmc0: autoconfiguration error: couldn't enable card: 60`
- Radeon VCE resume warning
- `audio0(hdafg0): audio_drain: device timeout` on Intel HDMI/DP audio

The Realtek ALC280 is the intended built-in analog audio device and is now the default.

## Installation status

- The rebuilt ADJUSTED kernel (SHA256 `d2529c24c507ed0ffe22e38a46b1cd0684fcdb26a3ba06cf8de1f76930dc9741`) has been installed as `/netbsd` for normal boot testing.
- `/netbsd.GENERIC` and `/netbsd.pre-adjusted` are retained as recovery kernels.
- A normal reboot and post-boot identity check are still required before this installation is counted as verified.

## Remaining checks

Before replacing the normal `/netbsd` kernel permanently:

- Associate `iwm0` with a Wi-Fi network and verify traffic; the interface is present and RUNNING but currently has no SSID and reports `status: no network`.
- Confirm audible speaker/headphone playback and microphone capture on the Realtek codec.
- Suspend/resume and lid-close handling are intentionally out of scope for this kernel configuration. Battery and ACPI sensor reporting remain enabled and have already been verified.
- Keep `/netbsd.GENERIC` as a recovery kernel even after making ADJUSTED the default.
