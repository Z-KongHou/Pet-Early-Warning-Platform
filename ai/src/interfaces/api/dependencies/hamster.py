from application.analyze_hamster import AnalyzeHamsterUseCase
from interfaces.ioc.container import get_analyze_hamster_use_case


def get_analyze_hamster_use_case_dep() -> AnalyzeHamsterUseCase:
    return get_analyze_hamster_use_case()
