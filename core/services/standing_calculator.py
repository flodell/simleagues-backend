from core.models.championship import Standing
from core.models.choices import ParticipantType, RaceStatus
from core.models.race import RaceResult


class StandingCalculator:

    @staticmethod
    def recalculate(standing: Standing):
        """
        Recalculate standings from race results.

        For INDIVIDUAL championship: aggregates driver's results
        For TEAM championship: aggregates team's results
        """

        # Get results based on championship type
        if standing.championship.participant_type == ParticipantType.INDIVIDUAL:
            results = RaceResult.objects.filter(
                race__championship=standing.championship,
                race__status=RaceStatus.COMPLETED,
                race_entry__championship_entry=standing.participant,
            )
        else:
            results = RaceResult.objects.filter(
                race__championship=standing.championship,
                race__status=RaceStatus.COMPLETED,
                race_entry__championship_entry__team=standing.team,
            )

        # Aggregate points and stats
        standing.total_points = sum(r.points for r in results)
        standing.races_completed = results.count()
        standing.wins = results.filter(position=1).count()
        standing.podiums = results.filter(position__lte=3).count()
        standing.fastest_laps = results.filter(fastest_lap=True).count()
        standing.dnf_count = results.filter(dnf=True).count()
        standing.dsq_count = results.filter(dsq=True).count()

        # Best finish
        best_result = results.order_by("position").first()
        standing.best_finish = best_result.position if best_result else None

        standing.save()
