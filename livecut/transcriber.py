from typing import List, Dict, Any
from pathlib import Path


class WhisperTranscriber:
    def __init__(self, model_name: str = "small", language: str = "pt",
                 compute_type: str = "int8", device: str = "cpu",
                 beam_size: int = 5, vad_filter: bool = True,
                 word_timestamps: bool = True):
        self.model_name = model_name
        self.language = language
        self.compute_type = compute_type
        self.device = device
        self.beam_size = beam_size
        self.vad_filter = vad_filter
        self.word_timestamps = word_timestamps
        self.model = None

    def load_model(self) -> None:
        if self.model is not None:
            return

        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise ImportError(
                "faster-whisper is not installed. "
                "Install with: pip install faster-whisper"
            )

        try:
            self.model = WhisperModel(
                self.model_name,
                device=self.device,
                compute_type=self.compute_type
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to load Whisper model '{self.model_name}': {str(e)}"
            )

    def transcribe(self, audio_path: str) -> Dict[str, Any]:
        self.load_model()

        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        try:
            segments, info = self.model.transcribe(
                str(audio_path),
                language=self.language,
                beam_size=self.beam_size,
                word_timestamps=self.word_timestamps,
                vad_filter=self.vad_filter,
                vad_parameters=dict(min_silence_duration_ms=500)
            )
        except Exception as e:
            raise RuntimeError(f"Transcription failed: {str(e)}")

        segments_list = []
        words_list = []

        for segment in segments:
            segment_words = []
            if segment.words:
                for word in segment.words:
                    word_data = {
                        "word": word.word.strip(),
                        "start": word.start,
                        "end": word.end,
                        "probability": word.probability
                    }
                    segment_words.append(word_data)
                    words_list.append(word_data)

            segment_data = {
                "start": segment.start,
                "end": segment.end,
                "text": segment.text.strip(),
                "avg_logprob": segment.avg_logprob,
                "words": segment_words
            }
            segments_list.append(segment_data)

        all_language_probs = []
        if hasattr(info, 'all_language_probs') and info.all_language_probs:
            for lang, prob in info.all_language_probs:
                all_language_probs.append({
                    "language": lang,
                    "probability": prob
                })

        return {
            "segments": segments_list,
            "words": words_list,
            "language": info.language,
            "info": {
                "duration": info.duration,
                "all_language_probs": all_language_probs
            }
        }

    def get_word_transcripts(self, transcription: Dict[str, Any]) -> List[Dict[str, Any]]:
        word_list = []
        for segment in transcription.get("segments", []):
            for word in segment.get("words", []):
                word_list.append({
                    "word": word["word"],
                    "start": word["start"],
                    "end": word["end"],
                    "probability": word["probability"]
                })
        return word_list
