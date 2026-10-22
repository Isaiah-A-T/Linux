-- Force sRGB colorimetry so gamescope never sets BT2020_RGB on the PS5's
-- DP connector: the internal DP->HDMI bridge can't translate it and the
-- screen goes black.
gamescope.config.known_displays.lumen_ps5_srgb = {
    pretty_name = "PS5 HDMI (sRGB)",
    hdr = {
        supported = false,
        force_enabled = false,
        eotf = gamescope.eotf.gamma22,
        max_content_light_level = 400,
        max_frame_average_luminance = 400,
        min_content_light_level = 0.5
    },
    colorimetry = {
        r = { x = 0.640, y = 0.330 },
        g = { x = 0.300, y = 0.600 },
        b = { x = 0.150, y = 0.060 },
        w = { x = 0.3127, y = 0.3290 }
    },
    matches = function(display)
        return 100
    end
}
