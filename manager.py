import json
import logging
import os
import sys

from game.attack import AttackCache
from game.reports import ReportCache


class VillageManager:
    @staticmethod
    def farm_manager(verbose=False, clean_reports=False):
        logger = logging.getLogger("FarmManager")
        try:
            with open("config.json", "r") as f:
                config = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Error loading config file: {e}")
            return

        if verbose:
            logger.info("Villages: %d", len(config["villages"]))
        attacks = AttackCache.cache_grab()
        reports = ReportCache.cache_grab()

        if verbose:
            logger.info("Reports: %d", len(reports))
            logger.info("Farms: %d", len(attacks))
        t = {"wood": 0, "iron": 0, "stone": 0}
        
        def process_reports(reports, farm, data, verbose):
            num_attack = []
            loot = {"wood": 0, "iron": 0, "stone": 0}
            total_loss_count = 0
            total_sent_count = 0
            for rep in reports:
                if reports[rep]["dest"] == farm and reports[rep]["type"] == "attack":
                    for unit in reports[rep]["extra"]["units_sent"]:
                        total_sent_count += reports[rep]["extra"]["units_sent"][unit]
                    for unit in reports[rep]["extra"]["units_losses"]:
                        total_loss_count += reports[rep]["extra"]["units_losses"][unit]
                    try:
                        res = reports[rep]["extra"]["loot"]
                        for r in res:
                            loot[r] = loot[r] + int(res[r])
                            t[r] = t[r] + int(res[r])
                        num_attack.append(reports[rep])
                    except KeyError:
                        pass
            return num_attack, loot, total_loss_count, total_sent_count

        def calculate_percentage_lost(total_loss_count, total_sent_count):
            if total_sent_count > 0:
                return total_loss_count / total_sent_count * 100
            return 0

        def log_farm_info(logger, verbose, perf, farm, num_attack, loot, total_loss_count, percentage_lost):
            if verbose:
                logger.info(
                    "%sFarm village %s attacked %d times - Total loot: %s - Total units lost: %d (%.2f)",
                    perf, farm, len(num_attack), str(loot), total_loss_count, percentage_lost
                )

        for farm in attacks:
            data = attacks[farm]
            num_attack, loot, total_loss_count, total_sent_count = process_reports(reports, farm, data, verbose)
            percentage_lost = calculate_percentage_lost(total_loss_count, total_sent_count)

            perf = ""
            if data["high_profile"]:
                perf = "High Profile "
            if "low_profile" in data and data["low_profile"]:
                perf = "Low Profile "
            log_farm_info(logger, verbose, perf, farm, num_attack, loot, total_loss_count, percentage_lost)

            if len(num_attack):
                total = sum(loot.values())
                if len(num_attack) > 3:
                    if total / len(num_attack) < 100 and ("low_profile" not in data or not data["low_profile"]):
                        if verbose:
                            logger.info("Farm %s has very low resources (%d avg total), extending farm time", farm, total / len(num_attack))
                        data["low_profile"] = True
                        AttackCache.set_cache(farm, data)
                    elif total / len(num_attack) > 500 and ("high_profile" not in data or not data["high_profile"]):
                        if verbose:
                            logger.info("Farm %s has very high resources (%d avg total), setting to high profile", farm, total / len(num_attack))
                        data["high_profile"] = True
                        AttackCache.set_cache(farm, data)

            if percentage_lost > 20 and not data["low_profile"]:
                logger.warning(f"Dangerous {percentage_lost} percentage lost units! Extending farm time")
                data["low_profile"] = True
                data["high_profile"] = False
                AttackCache.set_cache(farm, data)
            if percentage_lost > 50 and len(num_attack) > 10:
                logger.critical("Farm seems too dangerous/ unprofitable to farm. Setting safe to false!")
                data["safe"] = False
                AttackCache.set_cache(farm, data)

        if verbose:
            logger.info("Total loot: %s" % t)

        if clean_reports:
            list_of_files = sorted(["./cache/reports/" + f for f in os.listdir("./cache/reports/")],
                                   key=os.path.getctime)

            logger.info(f"Found {len(list_of_files)} files")

            while len(list_of_files) > clean_reports:
                oldest_file = list_of_files.pop(0)
                logger.info(f"Delete old report ({oldest_file})")
                os.remove(os.path.abspath(oldest_file))


if __name__ == "__main__":
    logging.basicConfig(stream=sys.stdout)
    VillageManager.farm_manager(verbose=True)
