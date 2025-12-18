"""Asset system robustness improvements.

Provides:
- JSON schema validation for asset files
- Asset versioning support
- Safe asset loading with error recovery
- Asset metadata validation
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
import hashlib


class AssetValidator:
    """Validates asset JSON files against schema."""
    
    # Asset JSON schema
    ASSET_SCHEMA = {
        "version": str,
        "assets": list,
    }
    
    ASSET_ITEM_SCHEMA = {
        "name": str,
        "path": str,
        "type": str,  # "MASK" or "FILTER"
        "category": str,
        "thumbnail": str,  # Optional
        "description": str,  # Optional
    }
    
    @classmethod
    def validate_asset_file(cls, filepath: str) -> tuple[bool, List[str]]:
        """Validate asset JSON file.
        
        Args:
            filepath: Path to asset JSON file
            
        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []
        
        # Check file exists
        if not os.path.exists(filepath):
            return False, [f"Asset file not found: {filepath}"]
        
        # Check file is readable
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            return False, [f"Invalid JSON in {filepath}: {str(e)}"]
        except IOError as e:
            return False, [f"Cannot read {filepath}: {str(e)}"]
        
        # Validate top-level structure
        if not isinstance(data, dict):
            errors.append("Asset file must be a JSON object")
            return False, errors
        
        if "version" not in data:
            errors.append("Missing 'version' field")
        elif not isinstance(data["version"], str):
            errors.append("'version' must be a string")
        
        if "assets" not in data:
            errors.append("Missing 'assets' array")
        elif not isinstance(data["assets"], list):
            errors.append("'assets' must be an array")
        else:
            # Validate each asset
            for i, asset in enumerate(data["assets"]):
                asset_errors = cls._validate_asset_item(asset, i)
                errors.extend(asset_errors)
        
        return len(errors) == 0, errors
    
    @classmethod
    def _validate_asset_item(cls, asset: Any, index: int) -> List[str]:
        """Validate individual asset item.
        
        Args:
            asset: Asset object to validate
            index: Index in assets array
            
        Returns:
            List of error messages
        """
        errors = []
        
        if not isinstance(asset, dict):
            errors.append(f"Asset {index} must be an object")
            return errors
        
        # Required fields
        required = ["name", "path", "type"]
        for field in required:
            if field not in asset:
                errors.append(f"Asset {index} missing required field: '{field}'")
            elif not isinstance(asset[field], str):
                errors.append(f"Asset {index} field '{field}' must be a string")
        
        # Validate type
        if "type" in asset and asset["type"] not in ["MASK", "FILTER"]:
            errors.append(f"Asset {index} type must be 'MASK' or 'FILTER', got '{asset['type']}'")
        
        return errors
    
    @classmethod
    def upgrade_asset_version(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Upgrade asset file to latest version.
        
        Args:
            data: Asset data dictionary
            
        Returns:
            Upgraded asset data
        """
        version = data.get("version", "1.0")
        
        # Version 1.0 → 2.0: Add metadata field
        if version == "1.0":
            data["version"] = "2.0"
            data["metadata"] = {
                "created": None,
                "modified": None,
                "checksum": None
            }
        
        return data


class AssetLoader:
    """Safely loads assets with error recovery."""
    
    @classmethod
    def load_asset_file(cls, filepath: str) -> Optional[Dict[str, Any]]:
        """Load asset file with error recovery.
        
        Args:
            filepath: Path to asset file
            
        Returns:
            Asset data or None on failure
        """
        # Validate first
        is_valid, errors = AssetValidator.validate_asset_file(filepath)
        
        if not is_valid:
            print(f"⚠️  Asset validation errors in {filepath}:")
            for error in errors:
                print(f"   - {error}")
            return None
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Upgrade if needed
            data = AssetValidator.upgrade_asset_version(data)
            
            return data
        except Exception as e:
            print(f"❌ Failed to load {filepath}: {str(e)}")
            return None
    
    @classmethod
    def load_asset_with_fallback(cls, 
                                 primary_path: str,
                                 fallback_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Load asset with fallback option.
        
        Args:
            primary_path: Primary asset file path
            fallback_path: Fallback path if primary fails
            
        Returns:
            Asset data from primary or fallback, or None
        """
        data = cls.load_asset_file(primary_path)
        
        if data is None and fallback_path:
            print(f"ℹ️  Trying fallback asset: {fallback_path}")
            data = cls.load_asset_file(fallback_path)
        
        return data


class AssetMetadata:
    """Manages asset metadata and versioning."""
    
    @staticmethod
    def calculate_checksum(filepath: str) -> str:
        """Calculate SHA256 checksum of file.
        
        Args:
            filepath: Path to file
            
        Returns:
            Hex checksum string
        """
        sha256_hash = hashlib.sha256()
        
        try:
            with open(filepath, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except IOError:
            return ""
    
    @staticmethod
    def validate_checksum(filepath: str, expected_checksum: str) -> bool:
        """Validate file checksum.
        
        Args:
            filepath: Path to file
            expected_checksum: Expected checksum value
            
        Returns:
            True if checksum matches
        """
        calculated = AssetMetadata.calculate_checksum(filepath)
        return calculated == expected_checksum
    
    @staticmethod
    def get_asset_info(filepath: str) -> Dict[str, Any]:
        """Get asset metadata.
        
        Args:
            filepath: Path to asset file
            
        Returns:
            Asset metadata dictionary
        """
        if not os.path.exists(filepath):
            return {}
        
        stat = os.stat(filepath)
        
        return {
            "path": filepath,
            "size": stat.st_size,
            "modified": stat.st_mtime,
            "checksum": AssetMetadata.calculate_checksum(filepath),
        }


class AssetRegistry:
    """Registry of all available assets."""
    
    def __init__(self):
        """Initialize asset registry."""
        self.assets: List[Dict[str, Any]] = []
        self.metadata: Dict[str, Dict[str, Any]] = {}
    
    def load_from_file(self, filepath: str) -> bool:
        """Load asset registry from file.
        
        Args:
            filepath: Path to asset registry file
            
        Returns:
            True if successful
        """
        data = AssetLoader.load_asset_file(filepath)
        
        if data is None:
            return False
        
        self.assets = data.get("assets", [])
        
        # Store metadata
        self.metadata["source"] = filepath
        self.metadata["info"] = AssetMetadata.get_asset_info(filepath)
        
        return True
    
    def get_assets_by_type(self, asset_type: str) -> List[Dict[str, Any]]:
        """Get all assets of specific type.
        
        Args:
            asset_type: Asset type ("MASK" or "FILTER")
            
        Returns:
            List of matching assets
        """
        return [a for a in self.assets if a.get("type") == asset_type]
    
    def get_asset_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get asset by name.
        
        Args:
            name: Asset name
            
        Returns:
            Asset data or None
        """
        for asset in self.assets:
            if asset.get("name") == name:
                return asset
        return None
    
    def validate_assets(self) -> tuple[int, int]:
        """Validate all assets in registry.
        
        Returns:
            Tuple of (valid_count, invalid_count)
        """
        valid = 0
        invalid = 0
        
        for asset in self.assets:
            # Check required fields
            if all(k in asset for k in ["name", "path", "type"]):
                # Try to verify file exists
                if os.path.exists(asset["path"]):
                    valid += 1
                else:
                    invalid += 1
            else:
                invalid += 1
        
        return valid, invalid
