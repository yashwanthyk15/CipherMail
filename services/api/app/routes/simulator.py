from fastapi import APIRouter

router = APIRouter()

@router.post("/simulator/launch")
async def launch_simulation(attack_type: str = "phishing"):
    # In a full implementation, this would trigger the attack-simulator service
    # via HTTP or Kafka to start sending emails to port 587.
    return {"status": "started", "attack_type": attack_type, "message": "Simulation launched successfully"}
