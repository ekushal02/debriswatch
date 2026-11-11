# Frontend acceptance checklist

The frontend is implemented and served at `/`. It uses the same-origin API, so it requires no frontend package installation. Automated browser validation could not run in the development workspace: Chromium failed to start because its required socket operation was blocked. JavaScript syntax and backend/static-resource checks are separate checks, not a substitute for this acceptance run.

Run these steps locally after starting the backend:

- At desktop and phone widths, confirm the demo banner, readable controls and no horizontal overflow.
- Upload the generated 10-second `samples/demo.avi`. Confirm the first frame and enabled Start button.
- Draw a convex polygon, finish it, then reset to the default area.
- Start with default thresholds. Confirm annotated boxes, track IDs, count, video time and job status update.
- Confirm three inspection findings and one priority finding. No finding should auto-resolve when objects disappear.
- Acknowledge one finding, view its evidence snapshot, then confirm removal. Check the unresolved count falls by one.
- Export CSV and verify four rows plus the header, including the resolved record.
- Upload again after completion. Confirm the new preview remains visible and can be used to draw a new zone.
- Start a second job and stop it early. Refresh the page; verify job/event history persists.
- Try an unsupported file, a concave zone and an invalid numeric threshold. Check that the error is readable and the UI recovers.
- On a supported host with `DW_ENABLE_CAMERA=1`, check the camera workflow separately.

The next frontend iteration should add paginated history navigation, keyboard-based polygon editing, accessibility review and acceptance screenshots. These items are not prerequisites for running the implemented demo.
