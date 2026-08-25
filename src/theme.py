"""Brand colors for the dashboard's custom KPI/nav cards.

Theme switching itself (light/dark, chart colors) is handled natively by
Streamlit via .streamlit/config.toml ([theme.light] / [theme.dark]) - that's
what makes the built-in Settings menu (top-right ⋮) show a working
theme switcher that also correctly themes Plotly charts.

A previous version of this module faked a theme toggle with a
st.session_state flag plus injected CSS overriding .stApp. That controlled
the page chrome but Plotly charts ignore it entirely - st.plotly_chart's
default theme="streamlit" reads Streamlit's *real* active theme, which the
fake toggle never touched. Hence: charts stuck on one look regardless of
the button. Native config.toml theming doesn't have that gap.

The only thing still styled with custom CSS here is the hand-built KPI/nav
cards on the Home page, since there's no native "stat card with icon"
widget. Colors for those are picked from st.context.theme.type so they
still match whichever theme (light/dark, or the user's OS preference via
"Use system setting") is actually active.
"""
from __future__ import annotations

import streamlit as st

# Brand palette (from the Risk Data Lab logo) - also mirrored in
# .streamlit/config.toml's chartCategoricalColors.
BRAND_BLUE = "#0B3D66"
BRAND_BLUE_LIGHT = "#2E86AB"
BRAND_GREEN = "#3FA84F"
BRAND_GREEN_LIGHT = "#7ED957"


def get_card_theme() -> dict:
    """Colors for the custom KPI/nav cards, matching the active native
    Streamlit theme (see .streamlit/config.toml).

    Note: st.context.theme.type only reflects a theme change once a real
    browser-triggered rerun happens (e.g. a widget interaction) - toggling
    the theme in the Settings menu alone does not itself cause a script
    rerun, so anything colored through this function stays on the old
    theme until some other interaction reruns the script. The World/Life/
    Non-life KPI cards render through render_kpi_card/render_sub_kpi_card
    instead (see common.py), which sidestep this by detecting the live
    theme client-side rather than through this function.
    """
    is_dark = st.context.theme.type == "dark"
    if is_dark:
        return {
            "card_bg": "#161f33",
            "border": "#26314a",
            "text_muted": "#9aa7bd",
            "shadow": "0 6px 20px rgba(0,0,0,0.35)",
            "dark": True,
        }
    return {
        "card_bg": "#fbf6ec",
        "border": "#ddcdac",
        "text_muted": "#5b6b7f",
        "shadow": "0 6px 20px rgba(15,45,75,0.08)",
        "dark": False,
    }


def inject_card_css() -> dict:
    """Injects CSS scoped to our own custom card classes only (does not
    touch Streamlit's native chrome/widgets - those follow config.toml).
    Call once near the top of the script, every rerun. Returns the color
    dict (see get_card_theme)."""
    t = get_card_theme()
    st.markdown(
        f"""
        <style>
        .imx-nav-card {{
            background: {t["card_bg"]};
            border: 1px solid {t["border"]};
            border-radius: 14px;
            padding: 16px 16px 6px 16px;
            box-shadow: {t["shadow"]};
            text-align: center;
        }}
        .imx-nav-card .imx-nav-icon {{ font-size: 26px; }}
        .imx-nav-card .imx-nav-title {{ font-weight: 700; margin-top: 6px; }}
        .imx-nav-card .imx-nav-desc {{
            font-size: 12px; color: {t["text_muted"]}; margin: 4px 0 10px 0; min-height: 32px;
        }}
        .imx-hero-title {{
            font-size: 40px; font-weight: 800; margin-bottom: 0; line-height: 1.1;
            background: linear-gradient(90deg, {BRAND_BLUE}, {BRAND_GREEN});
            -webkit-background-clip: text; background-clip: text; color: transparent;
        }}
        .imx-hero-subtitle {{ color: {t["text_muted"]}; font-size: 16px; margin-top: 4px; }}
        .imx-page-title {{
            font-size: 20px; font-weight: 800; margin: 0; line-height: 1.2;
            background: linear-gradient(90deg, {BRAND_BLUE}, {BRAND_GREEN});
            -webkit-background-clip: text; background-clip: text; color: transparent;
        }}
        .imx-tagline {{
            text-align: center; color: {t["text_muted"]}; font-style: italic;
            letter-spacing: .04em; font-size: 14px; margin-top: 8px;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    return t
