import os
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from pathlib import Path

from logo_core import (
    initialize_logo_worker,
    normalize_output_settings,
    open_rgba_image,
    process_logo_task,
    write_error_summary,
)


def stop_executor(executor):
    """Request a quick stop without pretending running image jobs can be killed everywhere."""
    terminate_workers = getattr(executor, "terminate_workers", None)
    if callable(terminate_workers):
        terminate_workers()
        return
    executor.shutdown(wait=False, cancel_futures=True)


def run_processing_worker(folder, logo_path, files, settings, conflict_policy, processing_queue, cancel_requested):
    errors = []
    successes = 0
    output_settings = normalize_output_settings(settings.get("output"))
    global_adjustments = settings.get("adjustments", {})
    photo_adjustments = settings.get("photo_adjustments", {})
    photo_crops = settings.get("photo_crops", {})
    output_dir = Path(folder) / output_settings["folder_name"]
    output_dir.mkdir(exist_ok=True)
    margin_settings = {
        "top": settings["m_top"],
        "bottom": settings["m_bottom"],
        "left": settings["m_left"],
        "right": settings["m_right"],
    }
    try:
        logo = open_rgba_image(logo_path)
    except (OSError, ValueError, RuntimeError) as error:
        processing_queue.put(("fatal", f"មិនអាចបើក Logo បានទេ: {error}"))
        return
    logo_payload = (logo.size, logo.tobytes("raw", "RGBA"))

    total = len(files)
    completed = 0
    next_index = 0
    pending = {}
    max_workers = min(max(1, os.cpu_count() or 1), total)
    executor = ProcessPoolExecutor(max_workers=max_workers, initializer=initialize_logo_worker, initargs=(logo_payload,))
    executor_stopped = False
    try:
        # Keep only a small queue of submitted jobs so cancel does not continue launching new files.
        while next_index < total or pending:
            if cancel_requested.is_set():
                stop_executor(executor)
                executor_stopped = True
                processing_queue.put(("cancelled", successes, errors, output_dir))
                return

            while next_index < total and len(pending) < max_workers and not cancel_requested.is_set():
                file_index = next_index + 1
                filename = files[next_index]
                task = (
                    folder,
                    filename,
                    file_index,
                    output_settings,
                    conflict_policy,
                    margin_settings,
                    settings["position"],
                    settings["logo_size"],
                    settings["opacity"],
                    photo_adjustments.get(filename, global_adjustments),
                    photo_crops.get(filename, {}),
                )
                pending[executor.submit(process_logo_task, task)] = filename
                next_index += 1

            if not pending:
                break

            done, _ = wait(pending, return_when=FIRST_COMPLETED, timeout=0.2)
            if not done:
                continue

            for future in done:
                filename = pending.pop(future)
                completed += 1
                try:
                    status, _index, processed_file, _output_path = future.result()
                    if status == "cancelled":
                        continue
                    successes += 1
                    filename = processed_file
                except (OSError, ValueError, RuntimeError) as error:
                    errors.append({"file": filename, "error": str(error)})
                    processing_queue.put(("error", filename, str(error)))
                except Exception as error:
                    errors.append({"file": filename, "error": f"Unexpected worker error: {error}"})
                    processing_queue.put(("error", filename, f"Unexpected worker error: {error}"))
                processing_queue.put(("progress", completed, total, filename))
    finally:
        if not executor_stopped:
            executor.shutdown(wait=not cancel_requested.is_set(), cancel_futures=True)

    if cancel_requested.is_set():
        processing_queue.put(("cancelled", successes, errors, output_dir))
        return
    if errors:
        write_error_summary(output_dir, errors)
    processing_queue.put(("done", successes, errors, output_dir))
