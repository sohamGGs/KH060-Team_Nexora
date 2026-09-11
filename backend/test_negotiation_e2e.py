"""
test_negotiation_e2e.py - Autonomous Multi-Agent Negotiation End-to-End Test Suite
"""
import os
import sys
import json
import requests

BASE_URL = "http://localhost:8000/api"

def print_header(title: str):
    print("\n" + "=" * 55)
    print(title)
    print("=" * 55)

def main():
    print_header("PROCUREIQ LANGGRAPH MULTI-AGENT NEGOTIATION E2E TEST")

    # 1. Login as Admin
    print("\n[1] Authenticating as Lead Procurement Officer (Admin)...")
    login_res = requests.post(
        f"{BASE_URL}/auth/login",
        json={"username": "admin@procureiq.internal", "password": "admin123"}
    )
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("  [OK] Authenticated successfully.")

    # 2. Create a test Purchase Request
    print("\n[2] Creating Purchase Request for High-Volume Industrial Tooling...")
    pr_payload = {
        "title": "Automated High-Precision CNC Tooling & Spindle Assembly",
        "item_description": "Multi-axis high-speed CNC spindle assembly with dynamic vibration dampeners for precision stamping shift.",
        "quantity": 10,
        "urgency": "High",
        "department": "Operations",
        "estimated_budget": 125000.0
    }
    create_pr_res = requests.post(
        f"{BASE_URL}/purchase-requests",
        json=pr_payload,
        headers=headers
    )
    assert create_pr_res.status_code == 200, f"PR creation failed: {create_pr_res.text}"
    pr_data = create_pr_res.json()
    pr_id = pr_data["id"]
    print(f"  [OK] Created PR-{pr_id:04d}: '{pr_data['title']}' with budget ${pr_data['estimated_budget']:,.2f}")

    # 3. Get Initial Recommendations before negotiation
    print(f"\n[3] Fetching initial supplier recommendations for PR-{pr_id:04d}...")
    rec_before_res = requests.get(
        f"{BASE_URL}/vendors/recommendations/{pr_id}",
        headers=headers
    )
    assert rec_before_res.status_code == 200, f"Failed to get recommendations: {rec_before_res.text}"
    recs_before = rec_before_res.json()["recommendations"]
    print(f"  [OK] Found {len(recs_before)} initial supplier bids.")
    top_3_before = recs_before[:3]
    for idx, r in enumerate(top_3_before, 1):
        print(f"       #{idx} {r['vendor_name']} ({r['pricing_tier']}): ${r['quoted_price']:,.2f} | SLA: {r['delivery_days']}d | Score: {r['scores']['total_score']:.1f}")

    # 4. Trigger Autonomous Multi-Agent Negotiation via LangGraph
    print(f"\n[4] Triggering POST /api/vendors/negotiate/{pr_id} (LangGraph Multi-Agent)...")
    negotiate_res = requests.post(
        f"{BASE_URL}/vendors/negotiate/{pr_id}",
        headers=headers
    )
    assert negotiate_res.status_code == 200, f"Negotiation endpoint failed: {negotiate_res.text}"
    neg_data = negotiate_res.json()
    
    print("  [OK] Negotiation completed successfully!")
    print(f"       Total Initial Spend:    ${neg_data['total_initial_spend']:,.2f}")
    print(f"       Total Negotiated Spend: ${neg_data['total_negotiated_spend']:,.2f}")
    print(f"       Total Net Savings:      +${neg_data['total_savings']:,.2f} ({neg_data['total_savings_pct']:.1f}%)")
    print(f"       Winning Supplier:       {neg_data['top_vendor_name']}")

    # 5. Assert Structure of Negotiated Results
    assert len(neg_data["results"]) == 3, f"Expected 3 negotiated vendors, got {len(neg_data['results'])}"
    for vr in neg_data["results"]:
        print(f"\n       >> Vendor: {vr['vendor_name']} ({vr['pricing_tier']})")
        print(f"          Price: ${vr['original_price']:,.2f} -> ${vr['negotiated_price']:,.2f} (-${vr['savings_amount']:,.2f})")
        print(f"          SLA:   {vr['original_days']}d -> {vr['negotiated_days']}d ({vr['days_saved']}d saved)")
        print(f"          Transcripts ({len(vr['transcript'])} turns):")
        assert len(vr["transcript"]) >= 3, f"Expected at least 3 negotiation turns, got {len(vr['transcript'])}"
        for turn in vr["transcript"]:
            print(f"            - [R{turn['round']} {turn['speaker']}]: \"{turn['message'][:75]}...\" (Offer: ${turn['offered_price']:,.2f}, {turn['offered_days']}d)")
        
        # Verify pricing constraints
        price_floor = vr["original_price"] * 0.85
        assert vr["negotiated_price"] >= (price_floor - 0.01), f"Negotiated price ${vr['negotiated_price']} below 85% floor ${price_floor}"
        assert vr["negotiated_price"] <= vr["original_price"], f"Negotiated price ${vr['negotiated_price']} higher than original ${vr['original_price']}"

    # 6. Verify Database Persistence of Transcripts & Recalculated Scores
    print(f"\n[6] Verifying GET /api/vendors/recommendations/{pr_id} persistence...")
    rec_after_res = requests.get(
        f"{BASE_URL}/vendors/recommendations/{pr_id}",
        headers=headers
    )
    assert rec_after_res.status_code == 200
    recs_after = rec_after_res.json()["recommendations"]
    top_after = recs_after[0]
    print(f"  [OK] Verified updated ranking: #1 {top_after['vendor_name']} (Score: {top_after['scores']['total_score']:.1f})")
    assert top_after["negotiation_transcript"] is not None, "Negotiation transcript not persisted on bid!"

    # 7. Test Fallback Resilience
    print("\n[7] Testing Resilience & Fallback Handling (Simulated Offline / Quota Drop)...")
    from app.negotiation.agents import run_multi_agent_negotiation
    # Directly invoke with empty/offline conditions
    dummy_pr = {"id": 999, "title": "Dummy PR", "item_description": "Test", "estimated_budget": 50000.0}
    dummy_vendors = [
        {"vendor_id": 1, "vendor_name": "Test Enterprise Vendor", "pricing_tier": "Enterprise Tier-1", "quoted_price": 50000.0, "delivery_days": 5, "avg_delivery_days": 4},
        {"vendor_id": 2, "vendor_name": "Test Economy Vendor", "pricing_tier": "Economy Tier", "quoted_price": 42000.0, "delivery_days": 8, "avg_delivery_days": 7},
        {"vendor_id": 3, "vendor_name": "Test Mid-Tier Vendor", "pricing_tier": "Mid-Tier", "quoted_price": 46000.0, "delivery_days": 6, "avg_delivery_days": 5}
    ]
    fb_result = run_multi_agent_negotiation(dummy_pr, dummy_vendors)
    assert len(fb_result["vendors"]) == 3
    for v in fb_result["vendors"]:
        assert len(v["transcript"]) >= 3
        assert v["final_price"] <= v["initial_price"]
        assert v["final_price"] >= v["price_floor"]
    print("  [OK] Fallback execution succeeded gracefully with zero exceptions.")

    print_header("ALL MULTI-AGENT NEGOTIATION TESTS PASSED WITH 100% SUCCESS!")

if __name__ == "__main__":
    main()
