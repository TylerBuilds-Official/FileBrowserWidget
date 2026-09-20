# Fluent System Icons

Selected regular SVGs from [Microsoft Fluent System Icons](https://github.com/microsoft/fluentui-system-icons), downloaded 2026-09-19.

- `checkmark.svg`: `assets/Checkmark/SVG/ic_fluent_checkmark_16_regular.svg`
- `chevron-down.svg`: `assets/Chevron Down/SVG/ic_fluent_chevron_down_16_regular.svg`

Copyright Microsoft Corporation. Distributed under the MIT license; see LICENSE and the upstream NOTICE.

These two are here because a Qt stylesheet can only point `image:` at a file, so the checkbox tick
and the combo box arrow cannot be drawn from a font. The `-light.svg` and `-dark.svg` variants
change only the fill colour; geometry is unchanged. `checkmark-light.svg` is the white tick, drawn
on a dark accent fill, and `checkmark-dark.svg` is the near-black one.

Every other icon in the app is a glyph from **Segoe Fluent Icons**, the icon font Windows draws its
own chrome with; see `ui/custom_widgets/fluent_icon_button.py`. Glyphs follow the theme colour and
the display scale on their own, so nothing needs tinting or re-rendering.
