from xmovie.core import (
    _check_plotfunc_output,
    _combine_ffmpeg_command,
    _execute_command,
    _check_ffmpeg_execute,
    frame_save,
    write_movie,
    convert_gif,
    Movie,
)
from xmovie.presets import basic, rotating_globe
import pytest
import matplotlib.pyplot as plt
from PIL import Image
import numpy as np
import xarray as xr
import os
import cv2


def dummy_plotfunc(da, fig, timestep):
    # a very simple plotfunc, which might be passed by the user
    ax = fig.subplots()
    da.isel(time=timestep).plot(ax=ax)


def test_check_plotfunc_output():
    da = xr.DataArray(np.random.rand(40, 60, 7), dims=["x", "y", "time"])
    assert _check_plotfunc_output(dummy_plotfunc, da) == 0
    assert _check_plotfunc_output(basic, da) == 2
    # TODO: I should loop over all presets with this test to ensure consistency


@pytest.mark.parametrize("w", [400, 1024])
@pytest.mark.parametrize("h", [400, 1024])
@pytest.mark.parametrize("dpi", [43, 150])
@pytest.mark.parametrize("frame", [0, 10, 100, 1000])
@pytest.mark.parametrize("frame_pattern", ["frame_%05d.png", "test%05d.png"])
def test_frame_save(tmpdir, frame, frame_pattern, dpi, w, h):
    # Create Figure
    # fig = plt.figure()
    fig = plt.figure(figsize=[w / dpi, h / dpi])
    frame_save(fig, frame, odir=tmpdir, frame_pattern=frame_pattern, dpi=dpi)
    filename = tmpdir.join(frame_pattern % frame)
    img = Image.open(filename.strpath)
    pixel_w, pixel_h = img.size
    # # Check if figure was properly closed
    assert filename.exists()
    assert not plt.fignum_exists(fig.number)
    assert pixel_w == w
    assert pixel_h == h


def test_check_ffmpeg_version():
    # ooof I will have to check this with the ci, one which has ffmpeg and one
    # which doesnt...Check xarray how to do this.
    pass


@pytest.mark.parametrize(
    "dir, fname, path", [("", "file", "file"), ("foo", "file", "foo/file")]
)
@pytest.mark.parametrize("frame_pattern", ["frame_%05d.png", "test%05d.png"])
@pytest.mark.parametrize("framerate", [5, 25])
@pytest.mark.parametrize(
    "ffmpeg_options",
    [
        "-c:v libx264 -preset veryslow -crf 10 -pix_fmt yuv420p",
        "-c:v libx264 -preset slow -crf 15 -pix_fmt yuv420p",
    ],
)
def test_combine_ffmpeg_command(
    dir, fname, path, frame_pattern, framerate, ffmpeg_options
):
    cmd = _combine_ffmpeg_command(dir, fname, framerate, frame_pattern, ffmpeg_options)
    assert cmd == 'ffmpeg -i "%s" -y %s -r %i "%s"' % (
        os.path.join(dir, frame_pattern),
        ffmpeg_options,
        framerate,
        path,
    )
    # TODO: needs more testing for the decomp of the movie filename.


def test_execute_command():
    a = _execute_command("ls -l")
    assert a.returncode == 0

    with pytest.raises(RuntimeError):
        _execute_command("ls -l?")


def test_check_ffmpeg_execute():
    # Same issue as `test_check_ffmpeg_version`

    a = _check_ffmpeg_execute("ls -l")
    assert a.returncode == 0

    with pytest.raises(RuntimeError):
        _check_ffmpeg_execute("ls -l?")


def test_dataarray():
    """Create a little test dataset"""
    x = np.arange(4)
    y = np.arange(5)
    t = np.arange(2)
    data = np.random.rand(len(x), len(y), len(t))
    return xr.DataArray(data, coords=[("x", x), ("y", y), ("time", t)])


@pytest.mark.parametrize("moviename", ["movie.mp4", "shmoovie.mp4"])
@pytest.mark.parametrize("remove_frames", [True, False])
@pytest.mark.parametrize("framerate", [5, 20])
@pytest.mark.parametrize(
    "ffmpeg_options",
    [
        "-c:v libx264 -preset veryslow -crf 10 -pix_fmt yuv420p",
        "-c:v libx264 -preset fast -crf 15 -pix_fmt yuv420p",
        # I am not sure how to assert the bitrate yet...
    ],
)
def test_write_movie(tmpdir, moviename, remove_frames, framerate, ffmpeg_options):

    frame_pattern = "frame_%05d.png"  # the default
    m = tmpdir.join(moviename)
    da = test_dataarray()
    mov = Movie(da)
    mov.save_frames(tmpdir)
    filenames = [tmpdir.join(frame_pattern % ff) for ff in range(len(da.time))]
    write_movie(
        tmpdir,
        moviename,
        remove_frames=remove_frames,
        framerate=framerate,
        ffmpeg_options=ffmpeg_options,
    )

    if remove_frames:
        assert all([~fn.exists() for fn in filenames])
    else:
        assert all([fn.exists() for fn in filenames])
    assert m.exists()  # could test more stuff here I guess.
    fps = cv2.VideoCapture(m.strpath).get(cv2.CAP_PROP_FPS)
    assert fps == framerate


@pytest.mark.parametrize("moviename", ["movie.mp4"])
@pytest.mark.parametrize("gif_palette", [True, False])
@pytest.mark.parametrize("gifname", ["movie.gif"])
@pytest.mark.parametrize("remove_movie", [True, False])
@pytest.mark.parametrize("gif_framerate", [10, 15])
def test_convert_gif(
    tmpdir, moviename, remove_movie, gif_palette, gifname, gif_framerate
):
    m = tmpdir.join(moviename)
    mpath = m.strpath
    g = tmpdir.join(gifname)
    gpath = g.strpath

    da = test_dataarray()
    mov = Movie(da)
    mov.save_frames(tmpdir)

    write_movie(tmpdir, moviename)

    convert_gif(
        mpath,
        gpath=gpath,
        gif_palette=gif_palette,
        remove_movie=remove_movie,
        gif_framerate=gif_framerate,
    )

    if remove_movie:
        assert ~m.exists()
    else:
        assert m.exists()

    assert g.exists()
    fps = 1000 / Image.open(g.strpath).info["duration"]
    assert np.ceil(fps) == gif_framerate

    # TODO: Better error message when framedim is not available.
    # This takes forever with all these options...
    # Check the overwrite option


@pytest.mark.parametrize("frame_pattern", ["frame_%05d.png", "test%05d.png"])
@pytest.mark.parametrize("pixelwidth", [100, 500, 1920])
@pytest.mark.parametrize("pixelheight", [100, 500, 1080])
# combine them and also add str specs like 'HD' '1080' '4k'
@pytest.mark.parametrize("framedim", ["time", "x", "wrong"])
@pytest.mark.parametrize("dpi", [50, 200])
@pytest.mark.parametrize("plotfunc", [None, rotating_globe, dummy_plotfunc])
def test_Movie(plotfunc, framedim, frame_pattern, dpi, pixelheight, pixelwidth):
    da = test_dataarray()
    kwargs = dict(
        plotfunc=plotfunc,
        framedim=framedim,
        frame_pattern=frame_pattern,
        pixelwidth=pixelwidth,
        pixelheight=pixelheight,
        dpi=dpi,
    )
    if framedim == "wrong":
        with pytest.raises(ValueError):
            mov = Movie(da, **kwargs)
    else:
        mov = Movie(da, **kwargs)

        if plotfunc is None:
            assert mov.plotfunc == basic
        else:
            assert mov.plotfunc == plotfunc
        assert mov.plotfunc_n_outargs == _check_plotfunc_output(mov.plotfunc, mov.data)

        assert mov.dpi == dpi
        assert mov.framedim == framedim
        assert mov.pixelwidth == pixelwidth
        assert mov.pixelheight == pixelheight
        assert mov.dpi == dpi
        assert mov.kwargs == {}
        # assures that none of the input options are not parsed


@pytest.mark.parametrize("frame_pattern", ["frame_%05d.png", "test%05d.png"])
def test_movie_save_frames(tmpdir, frame_pattern):
    da = test_dataarray()
    mov = Movie(da, frame_pattern=frame_pattern)
    mov.save_frames(tmpdir)
    filenames = [tmpdir.join(frame_pattern % ff) for ff in range(len(da.time))]
    assert all([fn.exists() for fn in filenames])


@pytest.mark.parametrize("filename", ["movie.mp4", "movie.gif"])
@pytest.mark.parametrize("gif_palette", [True, False])
@pytest.mark.parametrize("framerate, gif_framerate", [(10, 8), (24, 15), (7, 4)])
@pytest.mark.parametrize(
    "ffmpeg_options",
    [
        "-c:v libx264 -preset veryslow -crf 10 -pix_fmt yuv420p",
        "-c:v libx264 -preset slow -crf 15 -pix_fmt yuv420p",
    ],
)
def test_movie_save(
    tmpdir, filename, gif_palette, framerate, gif_framerate, ffmpeg_options
):
    print(gif_palette)
    # Need more tests for progress, verbose, overwriting
    path = tmpdir.join(filename)
    da = test_dataarray()
    mov = Movie(da)
    mov.save(
        path.strpath,
        gif_palette=gif_palette,
        framerate=framerate,
        gif_framerate=gif_framerate,
        ffmpeg_options=ffmpeg_options,
    )

    assert path.exists()
    # I should also check if no other files were created. For later

    # Check relevant fps of output file
    if ".mp4" in filename:
        fps = cv2.VideoCapture(path.strpath).get(cv2.CAP_PROP_FPS)
        assert fps == framerate
    elif ".gif" in filename:
        fps = 1000 / Image.open(path.strpath).info["duration"]
        assert np.ceil(fps) == gif_framerate

    # Check overwriting
    print(path.exists())
    with pytest.raises(RuntimeError):
        mov.save(path.strpath, overwrite_existing=False)