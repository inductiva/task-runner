"""Visualization utils to run inside containers."""
from typing import List

import moviepy.video.io.ImageSequenceClip


def create_movie_from_frames(frame_paths: List[str],
                             movie_path: str,
                             fps: int = 10) -> None:
    """Creates movie from a series of png image files.

    The order of the png image file names determines the order
    with which they are rendered in the movie. For example, image
    'frame-001.png' will appear before 'frame-002.png'.

    Args:
        frames_paths: List of paths for the frames to be compiled.
        movie_path: Path to the movie to be created.
        fps: Number of frames per second to use in the movie.
    """
    frames = sorted(frame_paths)

    # Generates the video.
    clip = moviepy.video.io.ImageSequenceClip.ImageSequenceClip(frames, fps=fps)
    clip.write_videofile(movie_path)
