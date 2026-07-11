#!/usr/bin/env python3
import subprocess
import sys
import os

os.chdir("/Users/twinssn/Projects/aikorea24")

cmd = """
ffmpeg -y \
-loop 1 -t 2.5 -i cards/card_1.png \
-loop 1 -t 2.5 -i cards/card_2.png \
-loop 1 -t 2.5 -i cards/card_3.png \
-loop 1 -t 2.5 -i cards/card_4.png \
-loop 1 -t 2.5 -i cards/card_5.png \
-i tts/narration_1.mp3 \
-i tts/narration_2.mp3 \
-i tts/narration_3.mp3 \
-i tts/narration_4.mp3 \
-i tts/narration_5.mp3 \
-filter_complex "
[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,zoompan=z='if(gte(zoom,1.12),1.12,zoom+0.0015)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=75:s=1080x1920:fps=30[v0];
[1:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,zoompan=z='if(gte(zoom,1.12),1.12,zoom+0.0015)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=75:s=1080x1920:fps=30[v1];
[2:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,zoompan=z='if(gte(zoom,1.12),1.12,zoom+0.0015)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=75:s=1080x1920:fps=30[v2];
[3:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,zoompan=z='if(gte(zoom,1.12),1.12,zoom+0.0015)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=75:s=1080x1920:fps=30[v3];
[4:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,zoompan=z='if(gte(zoom,1.12),1.12,zoom+0.0015)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=75:s=1080x1920:fps=30[v4];
[v0][v1]xfade=transition=wipeleft:duration=0.4:offset=1.9[v01];
[v01][v2]xfade=transition=circlecrop:duration=0.35:offset=3.8[v012];
[v012][v3]xfade=transition=dissolve:duration=0.4:offset=5.7[v0123];
[v0123][v4]xfade=transition=smoothleft:duration=0.4:offset=7.6[vout];
[5:a][6:a][7:a][8:a][9:a]concat=n=5:v=0:a=1[aout]
" \
-map "[vout]" -map "[aout]" \
-c:v h264_videotoolbox -c:a aac -b:a 128k \
-r 30 -pix_fmt yuv420p -shortest output_reel.mp4
"""

result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
print("STDOUT:", result.stdout[-2000:])
print("STDERR:", result.stderr[-3000:])
print("Return code:", result.returncode)