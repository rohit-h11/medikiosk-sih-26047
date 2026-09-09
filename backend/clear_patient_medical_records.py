"""
MediKiosk — Clear Patient Medical Records Script
Clears all clinical vectors, encounters, session logs, and storage artifacts for a given patient,
while keeping the patient's demographic ABHA profile fully intact.
"""

from app.db import get_supabase_client
try:
    from app.api.v1.endpoints.ocr import _patient_doc_cache
except ImportError:
    _patient_doc_cache = {}

def clear_patient_records(patient_id="PAT-ROHIT-01", abha_number="91-8824-3942-1092"):
    supabase = get_supabase_client()
    targets = [patient_id, abha_number, "rohit.hudlikar@abdm"]
    
    print(f"[CLEAR] Clearing medical records for targets: {targets}")
    
    # 1. Clear In-Memory OCR Caches
    for t in targets:
        if t in _patient_doc_cache:
            del _patient_doc_cache[t]
            print(f"  [OK] Cleared in-memory OCR cache for {t}")

    # 2. Clear patient_structured_vectors
    for t in targets:
        try:
            res = supabase.table("patient_structured_vectors").delete().eq("patient_id", t).execute()
            count = len(res.data) if res.data else 0
            print(f"  [OK] Deleted {count} rows from patient_structured_vectors for {t}")
        except Exception as e:
            print(f"  [WARN] Error deleting from patient_structured_vectors: {e}")

    # 3. Clear dialogue_sessions & cascade dialogue_messages
    for t in targets:
        try:
            res = supabase.table("dialogue_sessions").delete().eq("patient_id", t).execute()
            count = len(res.data) if res.data else 0
            print(f"  [OK] Deleted {count} rows from dialogue_sessions for {t}")
        except Exception as e:
            print(f"  [WARN] Error deleting from dialogue_sessions: {e}")

    # 4. Clear clinical_visits
    for t in targets:
        try:
            res = supabase.table("clinical_visits").delete().eq("patient_id", t).execute()
            count = len(res.data) if res.data else 0
            print(f"  [OK] Deleted {count} rows from clinical_visits for {t}")
        except Exception as e:
            print(f"  [WARN] Error deleting from clinical_visits: {e}")

    # 5. Clear Storage Buckets
    try:
        buckets = supabase.storage.list_buckets()
        for b in buckets:
            bname = b.name
            try:
                for t in targets:
                    file_list = supabase.storage.from_(bname).list(t)
                    if file_list:
                        paths = [f"{t}/{f['name']}" for f in file_list]
                        supabase.storage.from_(bname).remove(paths)
                        print(f"  [OK] Removed {len(paths)} files from bucket [{bname}] under /{t}")
            except Exception:
                pass
    except Exception as e:
        print(f"  [WARN] Storage check: {e}")

    # 6. Verify Patient Demographic Record Still Exists
    prof = supabase.table("patients").select("*").eq("id", patient_id).execute()
    print("\n[VERIFIED] Patient Demographic Profile (Preserved):")
    if prof.data:
        p = prof.data[0]
        print(f"   Name: {p.get('name')}")
        print(f"   ABHA Number: {p.get('abha_number')}")
        print(f"   ABHA Address: {p.get('abha_address')}")
        print(f"   Phone: {p.get('phone')}")
        print(f"   Prakriti: {p.get('prakriti')}")
    else:
        print("   No patient profile found.")

if __name__ == "__main__":
    clear_patient_records()
