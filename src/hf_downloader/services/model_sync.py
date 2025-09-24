"""
Model status synchronization service for HF Downloader.

This module handles synchronization between models.json configuration
and database model status, with database status taking precedence.
"""

import json
from datetime import UTC, datetime
from typing import Any

from loguru import logger

from ..models.database import DatabaseManager


class ModelSyncService:
    """Service for synchronizing model status between JSON and database."""

    def __init__(self, db_manager: DatabaseManager, models_file_path: str):
        """Initialize model sync service."""
        self.db_manager = db_manager
        self.models_file_path = models_file_path

    def load_models_from_json(self) -> list[dict[str, Any]]:
        """Load models configuration from JSON file."""
        try:
            with open(self.models_file_path, encoding="utf-8") as f:
                config = json.load(f)
                return config.get("models", [])
        except FileNotFoundError:
            logger.warning(f"Models file not found: {self.models_file_path}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in models file: {e}")
            return []
        except Exception as e:
            logger.error(f"Error loading models from JSON: {e}")
            return []

    def save_models_to_json(
        self, models: list[dict[str, Any]], config: dict[str, Any] = None
    ) -> bool:
        """Save models configuration to JSON file."""
        try:
            # Load existing config to preserve settings and metadata
            existing_config = {}
            try:
                with open(self.models_file_path, encoding="utf-8") as f:
                    existing_config = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                pass

            # Update models array
            existing_config["models"] = models

            # Update metadata
            if "metadata" not in existing_config:
                existing_config["metadata"] = {}
            existing_config["metadata"]["last_updated"] = datetime.now(UTC).isoformat()

            # Save to file
            with open(self.models_file_path, "w", encoding="utf-8") as f:
                json.dump(existing_config, f, indent=2, ensure_ascii=False)

            logger.info(f"Saved {len(models)} models to JSON file")
            return True

        except Exception as e:
            logger.error(f"Error saving models to JSON: {e}")
            return False

    def get_model_status_from_db(self, model_name: str) -> str | None:
        """Get model status from database."""
        try:
            model = self.db_manager.get_model_by_name(model_name)
            return model.status if model else None
        except Exception as e:
            logger.error(f"Error getting model status from DB: {e}")
            return None

    def sync_models_from_json_to_db(self) -> dict[str, Any]:
        """
        Synchronize models from JSON to database.
        Creates new models in database if they don't exist.
        Updates existing models if they are in pending state or if JSON provides new metadata.
        Database status takes precedence for non-pending models.
        """
        try:
            json_models = self.load_models_from_json()
            sync_results = {
                "total_models": len(json_models),
                "added": 0,
                "updated": 0,
                "skipped": 0,
                "errors": [],
                "details": [],
            }

            for json_model in json_models:
                model_name = json_model.get("name")
                if not model_name:
                    sync_results["errors"].append("Model missing name field")
                    continue

                try:
                    db_model = self.db_manager.get_model_by_name(model_name)

                    if not db_model:
                        # Create new model in database
                        status = json_model.get("status", "pending")
                        metadata = {
                            "source": "json_config",
                            "priority": json_model.get("priority", "medium"),
                        }

                        # Filter out None values from metadata
                        metadata = {
                            k: v
                            for k, v in metadata.items()
                            if v is not None and v != ""
                        }

                        self.db_manager.create_model(
                            name=model_name, status=status, metadata=metadata
                        )

                        sync_results["added"] += 1
                        sync_results["details"].append(
                            {"model": model_name, "action": "created", "status": status}
                        )

                        logger.info(
                            f"Created new model in DB: {model_name} with status {status}"
                        )

                    else:
                        # 模型已存在，检查是否需要更新
                        json_status = json_model.get("status", "pending")
                        db_status = db_model.status

                        # 如果 JSON 中的 status 为空，使用数据库中的状态
                        if not json_model.get("status"):
                            sync_results["skipped"] += 1
                            sync_results["details"].append(
                                {
                                    "model": model_name,
                                    "action": "skipped",
                                    "db_status": db_status,
                                    "json_status": "pending",
                                }
                            )
                            logger.debug(
                                f"Model exists with empty status, using DB status: {model_name}"
                            )
                        # 如果数据库中的状态是 pending、failed，可以重置为 pending 进行重新下载
                        # 如果是 completed 或 downloading 状态，数据库状态优先，不能重置
                        elif db_status in ["pending", "failed"] and json_model.get(
                            "force_reset", False
                        ):
                            # 只有明确要求强制重置时，才将 pending/failed 状态重置为 pending
                            # 更新模型元数据
                            metadata = {
                                "source": "json_config",
                                "priority": json_model.get("priority", "medium"),
                            }

                            # 过滤掉空值
                            metadata = {
                                k: v
                                for k, v in metadata.items()
                                if v is not None and v != ""
                            }

                            # 更新模型信息，设置状态为 pending
                            self.db_manager.update_model(
                                db_model.id,
                                status="pending",
                                metadata=metadata,
                            )

                            sync_results["updated"] += 1
                            sync_results["details"].append(
                                {
                                    "model": model_name,
                                    "action": "updated",
                                    "db_status": db_status,
                                    "json_status": json_status,
                                }
                            )

                            logger.info(
                                f"Force reset model {model_name} to pending with updated metadata"
                            )
                        # 如果数据库中的状态是 completed 或 downloading，数据库状态优先
                        elif db_status in ["completed", "downloading"]:
                            sync_results["skipped"] += 1
                            sync_results["details"].append(
                                {
                                    "model": model_name,
                                    "action": "skipped",
                                    "db_status": db_status,
                                    "json_status": json_status,
                                }
                            )
                            logger.debug(
                                f"Model {model_name} is {db_status}, keeping DB status (has precedence)"
                            )
                        # 如果数据库状态是 pending 或 failed，但 JSON 也是 pending，不需要更新
                        elif db_status in ["pending", "failed"] and json_status == "pending":
                            sync_results["skipped"] += 1
                            sync_results["details"].append(
                                {
                                    "model": model_name,
                                    "action": "skipped",
                                    "db_status": db_status,
                                    "json_status": json_status,
                                }
                            )
                            logger.debug(
                                f"Model {model_name} is already {db_status}, no change needed"
                            )
                        else:
                            # 其他情况，数据库状态优先
                            sync_results["skipped"] += 1
                            sync_results["details"].append(
                                {
                                    "model": model_name,
                                    "action": "skipped",
                                    "db_status": db_status,
                                    "json_status": json_status,
                                }
                            )
                            logger.debug(
                                f"Model exists, DB status takes precedence: {model_name}"
                            )

                except Exception as e:
                    error_msg = f"Error syncing model {model_name}: {str(e)}"
                    sync_results["errors"].append(error_msg)
                    logger.error(error_msg)

            logger.info(
                f"Sync completed: {sync_results['added']} added, {sync_results.get('updated', 0)} updated, {sync_results['skipped']} skipped"
            )
            return sync_results

        except Exception as e:
            logger.error(f"Error during sync from JSON to DB: {e}")
            return {
                "total_models": 0,
                "added": 0,
                "updated": 0,
                "skipped": 0,
                "errors": [str(e)],
                "details": [],
            }

    def sync_db_status_to_json(self) -> dict[str, Any]:
        """
        Synchronize database model status back to JSON file.
        This updates the JSON status to match the database status.
        """
        try:
            json_models = self.load_models_from_json()
            db_models = self.db_manager.get_all_models()  # Need to add this method

            # Create mapping of model name to database status
            db_status_map = {model.name: model.status for model in db_models}

            sync_results = {
                "total_models": len(json_models),
                "updated": 0,
                "unchanged": 0,
                "errors": [],
                "details": [],
            }

            updated_models = []

            for json_model in json_models:
                model_name = json_model.get("name")
                if not model_name:
                    continue

                try:
                    db_status = db_status_map.get(model_name)
                    json_status = json_model.get("status", "pending")

                    if db_status and db_status != json_status:
                        # Update JSON status to match DB status
                        json_model["status"] = db_status
                        sync_results["updated"] += 1
                        sync_results["details"].append(
                            {
                                "model": model_name,
                                "old_status": json_status,
                                "new_status": db_status,
                                "source": "database",
                            }
                        )

                        logger.info(
                            f"Updated JSON status for {model_name}: {json_status} -> {db_status}"
                        )
                    else:
                        sync_results["unchanged"] += 1

                    updated_models.append(json_model)

                except Exception as e:
                    error_msg = f"Error syncing model {model_name}: {str(e)}"
                    sync_results["errors"].append(error_msg)
                    logger.error(error_msg)

            # Save updated models back to JSON
            if sync_results["updated"] > 0:
                self.save_models_to_json(updated_models)
                logger.info(f"Updated {sync_results['updated']} model statuses in JSON")

            return sync_results

        except Exception as e:
            logger.error(f"Error during sync from DB to JSON: {e}")
            return {
                "total_models": 0,
                "updated": 0,
                "unchanged": 0,
                "errors": [str(e)],
                "details": [],
            }

    def get_models_needing_sync(self) -> list[dict[str, Any]]:
        """Get models that have status differences between JSON and database."""
        try:
            json_models = self.load_models_from_json()
            sync_needed = []

            for json_model in json_models:
                model_name = json_model.get("name")
                if not model_name:
                    continue

                db_status = self.get_model_status_from_db(model_name)
                json_status = json_model.get("status", "pending")

                if db_status and db_status != json_status:
                    sync_needed.append(
                        {
                            "name": model_name,
                            "json_status": json_status,
                            "db_status": db_status,
                            "priority": json_model.get("priority", "medium"),
                        }
                    )

            return sync_needed

        except Exception as e:
            logger.error(f"Error getting models needing sync: {e}")
            return []

    def update_model_status_in_json(self, model_name: str, status: str) -> bool:
        """Update status of a specific model in JSON file."""
        try:
            json_models = self.load_models_from_json()
            updated = False

            for model in json_models:
                if model.get("name") == model_name:
                    old_status = model.get("status", "pending")
                    model["status"] = status
                    updated = True
                    logger.info(
                        f"Updated {model_name} status in JSON: {old_status} -> {status}"
                    )
                    break

            if updated:
                return self.save_models_to_json(json_models)
            else:
                logger.warning(f"Model {model_name} not found in JSON file")
                return False

        except Exception as e:
            logger.error(f"Error updating model status in JSON: {e}")
            return False


    def sync_status_changes_only(self) -> dict[str, Any]:
        """
        只同步状态变化，不改变模型的其他配置。
        专门用于下载过程中的状态同步。
        """
        try:
            json_models = self.load_models_from_json()
            db_models = self.db_manager.get_all_models()

            # Create mapping of model name to database status and metadata
            db_info_map = {}
            for model in db_models:
                db_info_map[model.name] = {
                    "status": model.status,
                    "download_path": model.download_path,
                    "updated_at": model.updated_at,
                }

            sync_results = {
                "total_models": len(json_models),
                "updated": 0,
                "unchanged": 0,
                "errors": [],
                "details": [],
            }

            updated_models = []

            for json_model in json_models:
                model_name = json_model.get("name")
                if not model_name:
                    continue

                try:
                    db_info = db_info_map.get(model_name)
                    if not db_info:
                        continue

                    json_status = json_model.get("status", "pending")
                    db_status = db_info["status"]

                    # 只在状态不同时更新
                    if db_status != json_status:
                        old_status = json_model["status"]
                        json_model["status"] = db_status

                        # 添加下载路径信息
                        if db_info["download_path"] and not json_model.get(
                            "download_path"
                        ):
                            json_model["download_path"] = db_info["download_path"]

                        sync_results["updated"] += 1
                        sync_results["details"].append(
                            {
                                "model": model_name,
                                "old_status": old_status,
                                "new_status": db_status,
                                "sync_type": "status_only",
                            }
                        )

                        logger.debug(
                            f"Status sync: {model_name} {old_status} -> {db_status}"
                        )
                    else:
                        sync_results["unchanged"] += 1

                    updated_models.append(json_model)

                except Exception as e:
                    error_msg = f"Error syncing status for {model_name}: {str(e)}"
                    sync_results["errors"].append(error_msg)
                    logger.error(error_msg)

            # 只在有更新时保存
            if sync_results["updated"] > 0:
                self.save_models_to_json(updated_models)
                logger.info(
                    f"Status sync completed: {sync_results['updated']} models updated"
                )

            return sync_results

        except Exception as e:
            logger.error(f"Error during status-only sync: {e}")
            return {
                "total_models": 0,
                "updated": 0,
                "unchanged": 0,
                "errors": [str(e)],
                "details": [],
            }

    def full_sync(self) -> dict[str, Any]:
        """Perform full synchronization between JSON and database."""
        try:
            logger.info("Starting full model synchronization")

            # Step 1: Sync from JSON to DB (create missing models)
            json_to_db_result = self.sync_models_from_json_to_db()

            # Step 2: Sync from DB to JSON (update statuses)
            db_to_json_result = self.sync_db_status_to_json()

            # Step 3: Get sync summary
            models_needing_sync = self.get_models_needing_sync()

            result = {
                "timestamp": datetime.now(UTC).isoformat(),
                "json_to_db": json_to_db_result,
                "db_to_json": db_to_json_result,
                "remaining_differences": len(models_needing_sync),
                "sync_needed_models": models_needing_sync,
                "success": len(json_to_db_result["errors"]) == 0
                and len(db_to_json_result["errors"]) == 0,
            }

            if result["success"]:
                logger.info("Full synchronization completed successfully")
            else:
                logger.warning("Full synchronization completed with errors")

            return result

        except Exception as e:
            logger.error(f"Error during full sync: {e}")
            return {
                "timestamp": datetime.now(UTC).isoformat(),
                "success": False,
                "error": str(e),
            }
