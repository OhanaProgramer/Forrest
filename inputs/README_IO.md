/io/ — Inputs Only

This isolates where frames come from.
	•	camera.py → webcam / live camera
	•	video_file.py → recorded run footage

Vision logic doesn’t care how frames arrive.

This is what lets you:
	•	Develop on Mac
	•	Deploy on Jetson
	•	Replay failures
