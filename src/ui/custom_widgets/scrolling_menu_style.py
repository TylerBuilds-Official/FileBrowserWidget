from PyQt6.QtWidgets import QProxyStyle, QStyle


class ScrollingMenuStyle(QProxyStyle):
    """Let a tall menu scroll, as Windows menus do; Qt would spread it into columns instead."""

    def styleHint(self, hint, option=None, widget=None, return_data=None):
        if hint == QStyle.StyleHint.SH_Menu_Scrollable:
            return 1

        return super().styleHint(hint, option, widget, return_data)
