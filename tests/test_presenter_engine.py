"""
Unit Tests for Full-Body Interactive Keynote Presenter Engine
"""

import pytest
from PIL import Image
from src.persona_manager import detect_persona
from src.presenter_engine import FullBodyKeynotePresenter


def test_presenter_initialization():
    persona = detect_persona("Google Gemini 2.5 Pro", "https://blog.google/technology")
    assert persona["id"] == "sundar_pichai"

    presenter = FullBodyKeynotePresenter(persona, width=544, height=960)
    assert presenter.accent_color == (66, 133, 244)
    assert presenter._head_cutout is not None
    assert presenter._head_cutout.mode == "RGBA"


def test_animate_head():
    persona = detect_persona("Google Gemini 2.5 Pro", "https://blog.google/technology")
    presenter = FullBodyKeynotePresenter(persona, width=544, height=960)

    # Test head animation with high speech amplitude
    head_img = presenter.animate_head(t=1.5, amp=0.65, gaze_angle=10.0, target_size=(140, 160))
    assert isinstance(head_img, Image.Image)
    assert head_img.size == (140, 160)
    assert head_img.mode == "RGBA"


def test_draw_presenter_greeting():
    persona = detect_persona("Google Gemini 2.5 Pro", "https://blog.google/technology")
    presenter = FullBodyKeynotePresenter(persona, width=544, height=960)

    canvas = Image.new("RGBA", (544, 960), (10, 15, 25, 255))
    finger_x, finger_y = presenter.draw_presenter(
        base_canvas=canvas,
        center_x=272,
        base_y=800,
        pose="GREETING",
        t=1.0,
        amp=0.3,
        scale=1.0,
    )
    assert isinstance(finger_x, int)
    assert isinstance(finger_y, int)


def test_draw_presenter_pointing_and_optical_beacon():
    persona = detect_persona("Google Gemini 2.5 Pro", "https://blog.google/technology")
    presenter = FullBodyKeynotePresenter(persona, width=544, height=960)

    canvas = Image.new("RGBA", (544, 960), (10, 15, 25, 255))
    target = (420, 260)
    finger_x, finger_y = presenter.draw_presenter(
        base_canvas=canvas,
        center_x=120,
        base_y=800,
        pose="POINT",
        t=2.0,
        amp=0.5,
        target_xy=target,
        scale=0.92,
    )
    assert finger_x > 120
    assert finger_y < 800

    # Draw optical beacon
    presenter.draw_interactive_optical_beacon(
        base_canvas=canvas,
        finger_xy=(finger_x, finger_y),
        target_xy=target,
        t=2.0,
    )


def test_persona_attire_variations():
    # Sam Altman (OpenAI)
    sam_p = detect_persona("OpenAI o3 reasoning model", "https://openai.com")
    sam_pres = FullBodyKeynotePresenter(sam_p)
    assert sam_pres.blazer_color == (48, 54, 62)

    # Jensen Huang (NVIDIA)
    jensen_p = detect_persona("NVIDIA Blackwell GPU Architecture", "https://nvidia.com")
    jensen_pres = FullBodyKeynotePresenter(jensen_p)
    assert jensen_pres.blazer_color == (15, 15, 18)


def test_get_stage_plate_center():
    persona = detect_persona("Google Gemini 2.5 Pro", "https://blog.google/technology")
    presenter = FullBodyKeynotePresenter(persona, width=544, height=960)

    plate_img, finger_xy = presenter.get_stage_plate("GREETING", t=1.0, amp=0.4)
    assert isinstance(plate_img, Image.Image)
    assert plate_img.size == (544, 960)
    assert isinstance(finger_xy, tuple)
    assert len(finger_xy) == 2


def test_get_stage_plate_pointing():
    persona = detect_persona("Google Gemini 2.5 Pro", "https://blog.google/technology")
    presenter = FullBodyKeynotePresenter(persona, width=544, height=960)

    plate_img, finger_xy = presenter.get_stage_plate("POINT", t=2.5, amp=0.7)
    assert isinstance(plate_img, Image.Image)
    assert plate_img.size == (544, 960)
    assert finger_xy == (492, 276)

    # Verify optical beacon can be drawn on this photorealistic plate
    presenter.draw_interactive_optical_beacon(
        base_canvas=plate_img,
        finger_xy=finger_xy,
        target_xy=(380, 158),
        t=2.5,
    )

