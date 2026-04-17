from __future__ import annotations


class CameraSystem:
    """Maps world-pixel coordinates to viewport (screen) coordinates.

    The **world** is a rectangle of size ``world_width × world_height`` pixels.
    The **viewport** is the visible canvas area of size
    ``viewport_width × viewport_height`` pixels.

    ``camera_x`` / ``camera_y`` are the world-pixel coordinates of the
    top-left corner of the viewport.  ``zoom`` is a linear scale factor —
    every world pixel occupies ``zoom`` screen pixels.

    Typical usage
    -------------
    ::

        cam = CameraSystem(viewport_w, viewport_h, world_w, world_h)
        cam.reset_view()          # fit entire world in viewport

        # On mouse-wheel scroll at screen position (ex, ey):
        cam.zoom_at(1.1, ex, ey)  # zoom in 10 %

        # On drag from (x0, y0) to (x1, y1):
        cam.pan(x1 - x0, y1 - y0)

        # To render organism at grid cell (cx, cy) with base cell size cs:
        sx, sy = cam.world_to_screen(cx * cs, cy * cs)
    """

    #: Allowed zoom range (0.25 × … 8 ×)
    MIN_ZOOM: float = 0.25
    MAX_ZOOM: float = 8.0

    def __init__(
        self,
        viewport_width: int,
        viewport_height: int,
        world_width: int,
        world_height: int,
    ) -> None:
        self.viewport_width: int = viewport_width
        self.viewport_height: int = viewport_height
        self.world_width: int = world_width
        self.world_height: int = world_height

        self.camera_x: float = 0.0  # world-pixel at left edge of viewport
        self.camera_y: float = 0.0  # world-pixel at top edge of viewport
        self.zoom: float = 1.0

        self.reset_view()

    # ── Coordinate conversion ─────────────────────────────────────────────────

    def world_to_screen(self, world_x: float, world_y: float) -> tuple[int, int]:
        """Convert world-pixel coordinates to screen-pixel coordinates."""
        sx = int((world_x - self.camera_x) * self.zoom)
        sy = int((world_y - self.camera_y) * self.zoom)
        return sx, sy

    def screen_to_world(self, screen_x: int, screen_y: int) -> tuple[float, float]:
        """Convert screen-pixel coordinates to world-pixel coordinates."""
        wx = screen_x / self.zoom + self.camera_x
        wy = screen_y / self.zoom + self.camera_y
        return wx, wy

    # ── Camera controls ───────────────────────────────────────────────────────

    def pan(self, dx: int, dy: int) -> None:
        """Translate the viewport by ``(dx, dy)`` **screen** pixels.

        Positive ``dx`` scrolls the map left (camera moves right in world space).
        Positive ``dy`` scrolls the map up.
        """
        self.camera_x -= dx / self.zoom
        self.camera_y -= dy / self.zoom
        self._clamp()

    def zoom_at(self, factor: float, screen_x: int, screen_y: int) -> None:
        """Zoom in (``factor`` > 1) or out (0 < ``factor`` < 1).

        The world point currently under ``(screen_x, screen_y)`` stays fixed
        on screen after the zoom.
        """
        wx, wy = self.screen_to_world(screen_x, screen_y)
        new_zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, self.zoom * factor))
        self.zoom = new_zoom
        # Re-align camera so the same world point stays under the cursor.
        self.camera_x = wx - screen_x / self.zoom
        self.camera_y = wy - screen_y / self.zoom
        self._clamp()

    def reset_view(self, ui_padding_x: int = 0, ui_padding_y: int = 0) -> None:
        """Fit the entire world into the viewport, offsetting for UI panel padding.

        Parameters
        ----------
        ui_padding_x:
            Horizontal screen pixels occupied by a UI panel on the left
            (e.g. the stats overlay).  The world will be fitted into the
            remaining area and rendered starting at screen-x = *ui_padding_x*
            so it is never hidden behind that panel.
        ui_padding_y:
            Vertical screen pixels occupied by a UI panel at the top.
        """
        if self.world_width <= 0 or self.world_height <= 0:
            return
        usable_w = max(1, self.viewport_width  - ui_padding_x)
        usable_h = max(1, self.viewport_height - ui_padding_y)
        zoom_x = usable_w / self.world_width
        zoom_y = usable_h / self.world_height
        self.zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, min(zoom_x, zoom_y)))
        # Centre the world inside the usable area, then shift right/down by
        # the padding so world(0,0) appears at screen_x = ui_padding_x.
        world_screen_w = self.world_width  * self.zoom
        world_screen_h = self.world_height * self.zoom
        extra_x = max(0.0, usable_w - world_screen_w)
        extra_y = max(0.0, usable_h - world_screen_h)
        offset_x = ui_padding_x + extra_x / 2
        offset_y = ui_padding_y + extra_y / 2
        # camera_x is the world-coordinate at the left edge of the viewport.
        # For world(0,0) to land at screen_x=offset_x:
        #   offset_x = (0 - camera_x) * zoom  =>  camera_x = -offset_x / zoom
        self.camera_x = -offset_x / self.zoom
        self.camera_y = -offset_y / self.zoom

    def get_visible_bounds(self) -> tuple[float, float, float, float]:
        """Return ``(min_wx, min_wy, max_wx, max_wy)`` in world-pixel coordinates.

        These are the world pixels currently visible inside the viewport.
        """
        min_wx = self.camera_x
        min_wy = self.camera_y
        max_wx = self.camera_x + self.viewport_width / self.zoom
        max_wy = self.camera_y + self.viewport_height / self.zoom
        return min_wx, min_wy, max_wx, max_wy

    # ── Internals ─────────────────────────────────────────────────────────────

    def _clamp(self) -> None:
        """Clamp camera to keep the world visible.

        The upper bounds prevent panning past the world's far edges.  The lower
        bounds allow *slightly negative* camera coordinates so that the world
        can be rendered offset from screen (0, 0) — this is used when a UI
        panel covers the top-left corner and we want to start the world to the
        right / below it.  The minimum is capped at ``-viewport / zoom`` so
        the world cannot be panned entirely off-screen.
        """
        max_cam_x = max(0.0, self.world_width  - self.viewport_width  / self.zoom)
        max_cam_y = max(0.0, self.world_height - self.viewport_height / self.zoom)
        min_cam_x = -(self.viewport_width  / self.zoom)
        min_cam_y = -(self.viewport_height / self.zoom)
        self.camera_x = max(min_cam_x, min(max_cam_x, self.camera_x))
        self.camera_y = max(min_cam_y, min(max_cam_y, self.camera_y))
