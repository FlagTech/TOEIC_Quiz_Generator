"""
COCO Caption Loader - 從 HuggingFace 下載 COCO 標註並本地緩存

用於 TOEIC Part 1 圖片描述題型，提供真實的圖片場景描述作為生成參考
"""

import json
import random
from pathlib import Path
from typing import Optional, List
from datasets import load_dataset
from backend.ai_clients.logger import get_logger

logger = get_logger(__name__)

# 數據存儲路徑
DATA_DIR = Path("data")
COCO_CACHE_FILE = DATA_DIR / "coco_captions.json"


class COCOCaptionLoader:
    """COCO 圖片標註載入器"""

    def __init__(self, cache_file: Path = COCO_CACHE_FILE):
        """
        初始化 COCO 標註載入器

        Args:
            cache_file: 快取檔案路徑（預設 data/coco_captions.json）
        """
        self.cache_file = cache_file
        self.captions: List[str] = []
        self._load_captions()

    def _load_captions(self):
        """載入標註數據（從快取或下載）"""
        # 檢查是否已有快取
        if self.cache_file.exists():
            logger.info(f"從快取載入 COCO 標註: {self.cache_file}")
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.captions = data['captions']
                logger.info(f"已載入 {len(self.captions)} 筆標註")
            except Exception as e:
                logger.error(f"載入快取失敗: {e}，將重新下載")
                self._download_and_cache()
        else:
            logger.info("快取不存在，開始下載 COCO 標註數據...")
            self._download_and_cache()

    def _download_and_cache(self):
        """從 HuggingFace 下載並快取數據"""
        try:
            # 下載數據集
            logger.info("正在下載 kknono668/Filtered-COCO-Captions...")
            ds = load_dataset("kknono668/Filtered-COCO-Captions", split="train")

            # 提取所有標註
            self.captions = [item['caption'] for item in ds]
            logger.info(f"已下載 {len(self.captions)} 筆標註")

            # 確保數據目錄存在
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)

            # 儲存到本地
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'captions': self.captions,
                    'count': len(self.captions),
                    'source': 'kknono668/Filtered-COCO-Captions'
                }, f, ensure_ascii=False, indent=2)

            logger.info(f"已快取標註數據到: {self.cache_file}")

        except Exception as e:
            logger.error(f"下載 COCO 標註失敗: {e}")
            raise Exception(f"無法下載 COCO 標註數據: {str(e)}")

    def get_random_caption(self) -> str:
        """
        獲取隨機標註

        Returns:
            隨機選擇的圖片描述文字

        Raises:
            ValueError: 標註數據為空
        """
        if not self.captions:
            raise ValueError("標註數據為空，請檢查數據載入是否成功")
        return random.choice(self.captions)

    def get_random_captions(self, count: int) -> List[str]:
        """
        獲取多筆隨機標註

        Args:
            count: 要取得的標註數量

        Returns:
            隨機選擇的圖片描述文字列表
        """
        if not self.captions:
            raise ValueError("標註數據為空，請檢查數據載入是否成功")
        return random.choices(self.captions, k=count)

    def get_caption(self, index: int) -> str:
        """
        根據索引獲取標註

        Args:
            index: 標註索引（0 到 len-1）

        Returns:
            指定索引的圖片描述文字
        """
        return self.captions[index]

    def refresh_cache(self):
        """強制重新下載並更新快取"""
        logger.info("強制重新下載 COCO 標註...")
        self._download_and_cache()

    def __len__(self) -> int:
        """返回標註數量"""
        return len(self.captions)


# 全局單例
_loader: Optional[COCOCaptionLoader] = None


def get_coco_caption_loader() -> COCOCaptionLoader:
    """
    獲取 COCO 標註載入器（單例模式）

    首次呼叫時會自動檢查本地快取，若不存在則從 HuggingFace 下載。
    後續呼叫直接使用已載入的數據。

    Returns:
        COCOCaptionLoader 實例
    """
    global _loader
    if _loader is None:
        _loader = COCOCaptionLoader()
    return _loader


def reload_coco_caption_loader() -> COCOCaptionLoader:
    """
    重新載入 COCO 標註載入器（用於強制更新）

    Returns:
        新的 COCOCaptionLoader 實例
    """
    global _loader
    _loader = COCOCaptionLoader()
    return _loader
