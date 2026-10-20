"""Render the saved 4-second animation and encode a portable H.264 MP4.
Run: blender -b Shotgun.blend --python scripts/render_animation.py
Requires ffmpeg on PATH; intermediate frames stay outside the checkout.
"""
import bpy, os, subprocess, shutil, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if Path(bpy.data.filepath).resolve() != (ROOT/'Shotgun.blend').resolve():
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/'Shotgun.blend'))
ffmpeg=shutil.which('ffmpeg')
if not ffmpeg: raise RuntimeError('Install ffmpeg to encode the animation preview.')
scene=bpy.context.scene
scene.camera=bpy.data.objects['Camera | hero']
scene.render.engine='CYCLES'; scene.cycles.device='CPU'; scene.cycles.samples=8; scene.cycles.use_denoising=True
scene.render.threads_mode='FIXED'; scene.render.threads=4
scene.render.resolution_x=640; scene.render.resolution_y=400; scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'; scene.render.use_persistent_data=True
frames=Path(os.environ.get('SHOTGUN_FRAMES_DIR') or tempfile.mkdtemp(prefix='shotgun-animation-'))
frames.mkdir(parents=True,exist_ok=True)
for frame in range(scene.frame_start,scene.frame_end+1):
    scene.frame_set(frame)
    target=frames/f'{frame:04d}.png'
    scene.render.filepath=str(target)
    bpy.ops.render.render(write_still=True)
    print(f'ANIMATION_FRAME {frame}/{scene.frame_end}',flush=True)
output=ROOT/'previews'/'Shotgun_Animation.mp4'; output.parent.mkdir(parents=True,exist_ok=True)
subprocess.run([ffmpeg,'-hide_banner','-loglevel','warning','-y','-framerate',str(scene.render.fps),'-start_number',str(scene.frame_start),'-i',str(frames/'%04d.png'),'-frames:v',str(scene.frame_end-scene.frame_start+1),'-c:v','libx264','-preset','slow','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(output)],check=True)
print('ANIMATION_SAVED',output,flush=True)
