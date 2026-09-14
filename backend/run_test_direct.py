import asyncio
import os
import io

from app.database import SessionLocal, engine, Base
from app.routers.upload import upload_files
from app.services.pipeline import execute
from app.models import UploadSession, PipelineRun
from fastapi import UploadFile

async def run_direct():
    files = [
        "../HPCL_Material_Master.xlsx", 
        "../BPCL_Material_Master.xlsx"
    ]
    
    from app.services.vector_service import reset_collection
    reset_collection()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    for filename in files:
        print(f"\n--- Testing {filename} ---")
        
        db = SessionLocal()
        try:
            with open(filename, "rb") as f:
                content = f.read()
                
            upload_file = UploadFile(filename=os.path.basename(filename), file=io.BytesIO(content))
            resp = await upload_files([upload_file], db=db)
            session_id = resp.sessions[0].id
            
            run = PipelineRun(upload_session_id=session_id)
            db.add(run)
            db.commit()
            
            await asyncio.to_thread(execute, run.id, 0.82, 0.75)
            
            session = db.query(UploadSession).filter(UploadSession.id == session_id).first()
            acc = session.accuracy_score
            print(f"FINAL ACCURACY for {os.path.basename(filename)}: {acc * 100 if acc else 0:.2f}%")
        except Exception as e:
            print(f"Error testing {filename}: {e}")
            import traceback
            traceback.print_exc()
        finally:
            db.close()

if __name__ == "__main__":
    asyncio.run(run_direct())
