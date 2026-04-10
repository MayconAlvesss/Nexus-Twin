import httpx
import asyncio
import random
from datetime import datetime, timezone

API_URL = "http://127.0.0.1:8000/api/v1"
API_KEY = "nexus-dev-key-change-me"

ELEMENTS = [
    {"element_id": "COL-001", "name": "Ground Floor Column A", "element_type": "COLUMN", "material_class": "concrete", "age_years": 12.5, "floor_level": "L0"},
    {"element_id": "COL-002", "name": "Main Support Column B", "element_type": "COLUMN", "material_class": "concrete", "age_years": 12.5, "floor_level": "L0"},
    {"element_id": "BM-012",  "name": "Level 3 Transfer Beam", "element_type": "BEAM",   "material_class": "steel",    "age_years": 8.2,  "floor_level": "L3"},
    {"element_id": "BM-013",  "name": "Roof Support Beam C",   "element_type": "BEAM",   "material_class": "steel",    "age_years": 2.1,  "floor_level": "Roof"},
    {"element_id": "SLB-007", "name": "Basement Slab C",       "element_type": "SLAB",   "material_class": "concrete", "age_years": 15.0, "floor_level": "B1"},
    {"element_id": "FND-001", "name": "Main Foundation Block", "element_type": "FOUNDATION", "material_class": "concrete", "age_years": 20.0, "floor_level": "B2"},
]

async def seed():
    async with httpx.AsyncClient(headers={"X-NexusTwin-API-Key": API_KEY}) as client:
        print("[SEED] Seeding NexusTwin database via API...")
        
        for el in ELEMENTS:
            # 1. Register Element
            print(f"  Registering {el['element_id']}...")
            await client.post(f"{API_URL}/elements", json=el)
            
            # 2. Add some history (10 snapshots)
            print(f"  generating history for {el['element_id']}...")
            for i in range(10):
                # Random health decline for some
                base_shi = 85 if "COL" in el["element_id"] else 60 if "BM-012" in el["element_id"] else 95
                shi = max(0, min(100, base_shi + random.uniform(-5, 5) - (i * 0.5)))
                
                payload = {
                    "element_id": el["element_id"],
                    "strain_readings": [random.uniform(100, 200) for _ in range(5)],
                    "vibration_readings": [random.uniform(0.5, 1.5) for _ in range(5)],
                    "temperature_readings": [random.uniform(20, 25) for _ in range(5)],
                    "miner_damage_ratio": 0.05 + (i * 0.01)
                }
                # We'll use the compute endpoint but override with random if needed? 
                # Actually, the compute endpoint calculates it. Let's just call it.
                await client.post(f"{API_URL}/health/compute", json=payload)

            # 3. Add an anomaly for the warning ones
            if el["element_id"] == "BM-012":
                print(f"  Injecting anomaly for {el['element_id']}...")
                anomaly = {
                    "element_id": el["element_id"],
                    "strain_value": 450.5,
                    "vibration_value": 8.2,
                    "temperature_value": 24.0,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                await client.post(f"{API_URL}/anomaly/detect", json=anomaly)

        print("\n[DONE] Seeding complete. Dashboard ready at http://127.0.0.1:5174")

if __name__ == "__main__":
    asyncio.run(seed())
