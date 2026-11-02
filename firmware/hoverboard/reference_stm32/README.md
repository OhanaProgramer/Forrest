# STM32 / EFeru FOC path — REFERENCE ONLY

This is the firmware path we prepared for a single-mainboard STM32F103/GD32F103
hoverboard (the Gyroor G13 we hoped for). **Jr's actual board is not this** — it
is an MM32SPIN05 split board, so the active path is the parent folder's README
and `mm32/`. Keep this only in case a future board uses an STM32F103 mainboard.

- `prepare.sh` — clones EFeru FOC at a pinned commit and applies Forrest settings
- `forrest_config.py` — the settings patch (VARIANT_USART, tank steering, bench limits)
