from __future__ import annotations

from typing import Protocol

from english_typing_trainer.models.pronunciation import PronunciationRequest, PronunciationResult, WordFeedback


class PronunciationAssessmentProvider(Protocol):
    name: str
    def assess(self, request: PronunciationRequest) -> PronunciationResult: ...


class AzurePronunciationAssessmentProvider:
    """Thin Azure Speech adapter. It is never selected without an explicit key and region."""
    name = "azure"
    def __init__(self, key: str, region: str) -> None: self.key=key.strip(); self.region=region.strip()

    def assess(self, request: PronunciationRequest) -> PronunciationResult:
        if not self.key or not self.region:
            return PronunciationResult("not_configured",self.name,message="请先在设置中配置 Azure Speech 区域和 Key。",error_code="not_configured")
        try:
            import azure.cognitiveservices.speech as speechsdk
        except ImportError:
            return PronunciationResult("failed",self.name,message="未安装 Azure Speech SDK，无法进行云端评分。",error_code="sdk_unavailable")
        try:
            config=speechsdk.SpeechConfig(subscription=self.key,region=self.region)
            audio=speechsdk.audio.AudioConfig(filename=str(request.audio_path))
            assessment=speechsdk.PronunciationAssessmentConfig(request.reference_text,"HundredMark",request.granularity,request.enable_miscue)
            if request.enable_prosody and request.locale == "en-US": assessment.enable_prosody_assessment()
            recognizer=speechsdk.SpeechRecognizer(speech_config=config,audio_config=audio,language=request.locale); assessment.apply_to(recognizer)
            recognized=recognizer.recognize_once_async().get()
            if recognized.reason != speechsdk.ResultReason.RecognizedSpeech:
                detail=getattr(recognized,"cancellation_details",None); code="azure_cancelled"; message=str(detail.reason if detail else "Azure 未返回可用评分。")
                return PronunciationResult("failed",self.name,error_code=code,message=message)
            result=speechsdk.PronunciationAssessmentResult(recognized)
            words=[]
            for word in result.words or []:
                words.append(WordFeedback(word.word,word.accuracy_score,getattr(word,"error_type","None").name if hasattr(getattr(word,"error_type",None),"name") else str(getattr(word,"error_type","None"))))
            return PronunciationResult("completed",self.name,result.pronunciation_score,result.accuracy_score,result.fluency_score,result.completeness_score,getattr(result,"prosody_score",None),words,getattr(recognized,"result_id","") or "")
        except Exception as exc:
            return PronunciationResult("failed",self.name,error_code="azure_request_failed",message=str(exc))


class FakePronunciationAssessmentProvider:
    """Deterministic test-only provider. Production UI never creates this provider."""
    name="fake"
    def assess(self, request: PronunciationRequest) -> PronunciationResult:
        return PronunciationResult("completed",self.name,88.0,90.0,86.0,92.0,84.0,[WordFeedback(word,90.0) for word in request.reference_text.split()])
