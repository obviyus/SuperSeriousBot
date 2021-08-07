import subprocess
from typing import TYPE_CHECKING

from .ffprobe import FFProbe

if TYPE_CHECKING:
    import telegram
    import telegram.ext


def is_number(s):
    """ Returns True if string is a number. """
    return s.replace('.', '', 1).isdigit()


class StabVid(object):
    def __init__(
        self,
        ffmpeg_full_path="/usr/bin/ffmpeg",
        video_scale_factor="1.15",
        video_zoom_factor="-15",
        max_video_length_seconds=240
    ):
        self.max_video_length_seconds = max_video_length_seconds
        self.min_video_length_seconds = 1
        self.ffmpeg_full_path = ffmpeg_full_path
        self.video_scale_factor = video_scale_factor
        self.video_zoom_factor = video_zoom_factor

    def __call__(self, input_path, output_path, cropped=False):
        return self.stab_file(input_path, output_path, cropped)

    def stab_file(self, input_path, output_path, cropped=False):
        zoomed_file_name = "zoomed.mp4"
        metadata = FFProbe(input_path)
        if len(metadata.video) > 1:
            raise Exception("Video may not contain multiple video streams.")
        if len(metadata.video) < 1:
            raise Exception("No video streams found in file.")

        could_check_dur_initially = self.check_vid_duration(input_path)

        try:
            # zoom by the size of the zoom in the stabilization, the total output file is bigger,
            # but no resolution is lost to the crop
            subprocess.check_output(
                [self.ffmpeg_full_path,
                 "-y",
                 "-i", input_path,
                 "-vf", "scale=trunc((iw*" + self.video_scale_factor + ")/2)*2:trunc(ow/a/2)*2",
                 "-pix_fmt", "yuv420p",  # workaround for https://github.com/georgmartius/vid.stab/issues/36
                 zoomed_file_name],
                stderr=subprocess.STDOUT
            )

            if not could_check_dur_initially:
                # sometimes metadata on original vids were broken,
                # so we need to re-check after fixing it during the first ffmpeg-pass
                self.check_vid_duration(zoomed_file_name)

            subprocess.check_output(
                [self.ffmpeg_full_path,
                 "-y",
                 "-i", zoomed_file_name,
                 "-vf", "vidstabdetect",
                 "-f", "null",
                 "-"],
                stderr=subprocess.STDOUT
            )

            if cropped:
                subprocess.check_output(
                    [self.ffmpeg_full_path,
                     "-y",
                     "-i", zoomed_file_name,
                     "-vf", "vidstabtransform=smoothing=20:zoom=" + self.video_zoom_factor + ":optzoom=2"
                     + ":interpol=linear,unsharp=5:5:0.8:3:3:0.4",
                     output_path],
                    stderr=subprocess.STDOUT
                )
            else:
                subprocess.check_output(
                    [self.ffmpeg_full_path,
                     "-y",
                     "-i", zoomed_file_name,
                     "-vf", "vidstabtransform=smoothing=20:crop=black:zoom=" + self.video_zoom_factor
                     + ":optzoom=0:interpol=linear,unsharp=5:5:0.8:3:3:0.4",
                     output_path],
                    stderr=subprocess.STDOUT
                )
        except subprocess.CalledProcessError:
            raise Exception("ffmpeg couldn't compute file")

    def check_vid_duration(self, path):
        metadata = FFProbe(path)
        if hasattr(metadata.video[0], "duration") \
                and is_number(metadata.video[0].duration):
            if float(metadata.video[0].duration) > self.max_video_length_seconds:
                raise Exception(
                    "Video too long. Video duration: " + round(metadata.video[0].duration, 2)
                    + "s, Maximum duration: " + str(self.max_video_length_seconds) + "s. "
                )
            elif float(metadata.video[0].duration) < self.min_video_length_seconds:
                raise Exception(
                    "Video too short. Video duration: " + round(metadata.video[0].duration, 2)
                    + "s, Minimum duration: " + str(self.min_video_length_seconds) + "s. "
                )
            else:
                return True
        return False


def stab(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Stabilize a GIF or video"""
    if update.message:
        message: 'telegram.Message' = update.message
    else:
        return

    try:
        if message.reply_to_message.video:
            file_id = message.reply_to_message.video.file_id
        elif message.reply_to_message.animation:
            file_id = message.reply_to_message.animation.file_id
        else:
            message.reply_text(
                text="No `file_id` found."
            )
            return
        file: telegram.File = context.bot.get_file(file_id)
        file.download("/tmp/ssgbot.mp4")

        try:
            stabilizer = StabVid()
            stabilizer(
                "/tmp/ssgbot.mp4", "/tmp/ssgbot-stabbed.mp4", context.args[0] == "crop" if context.args else False
            )
            message.reply_animation(
                animation=open("/tmp/ssgbot-stabbed.mp4", "rb")
            )
        except Exception as e:
            message.reply_text(
                text=f'`{e.__str__()}`'
            )
    except AttributeError:
        message.reply_text(
            text="*Usage:* `/stab crop` "
                 "Reply to a GIF/video with `/stab` to stabilize it. Add `crop` to get rid of black borders.\n"
        )
