from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from . import crud, models, schemas, security, email_sender, cors
from .database import SessionLocal, engine
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins in development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

models.Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/test/email")
async def test_email():
    """Test route to verify email configuration"""
    try:
        success = email_sender.send_otp_email(
            "test@example.com", 
            "123456"
        )
        if success:
            return {"status": "success", "message": "Test email sent successfully"}
        return {"status": "error", "message": "Failed to send test email"}
    except Exception as e:
        return {
            "status": "error",
            "message": "Email configuration error",
            "details": str(e)
        }

@app.post("/signup", response_model=schemas.User)
def signup(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    return crud.create_user(db=db, user=user)

@app.post("/login", response_model=schemas.Token)
def login(user: schemas.UserLogin, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_email(db, email=user.email)
    logger.info(f"Login attempt for email: {user.email}")
    if not db_user or not security.verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    access_token = security.create_access_token(data={"sub": db_user.email})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": db_user
    }

@app.post("/contact-us")
def contact_us(contact: schemas.ContactUsCreate, db: Session = Depends(get_db)):
    new_contact = crud.create_contact_us(db=db, contact=contact)
    email_sender.send_contact_confirmation(to_email=contact.email, name=contact.name)
    return {"message": "Contact request submitted successfully"}

@app.post("/forgot-password/send-otp")
def send_forgot_password_otp(request: schemas.ForgotPasswordRequest, db: Session = Depends(get_db)):
    logger.info(f"OTP request for email: {request.email}")
    user = crud.get_user_by_email(db, request.email)
    if not user:
        logger.warning(f"User not found for email: {request.email}")
        raise HTTPException(status_code=404, detail="User not found")

    try:
        otp = crud.create_otp(db, request.email)
        logger.info(f"OTP generated for email: {request.email}")
        
        if email_sender.send_otp_email(request.email, otp):
            logger.info(f"OTP sent successfully to: {request.email}")
            return {"message": "OTP sent to email"}
        else:
            logger.error(f"Failed to send OTP email to: {request.email}")
            raise HTTPException(status_code=500, detail="Failed to send OTP email. Please try again.")
    except Exception as e:
        logger.error(f"Error in OTP process: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process OTP request. Please try again.")

@app.post("/forgot-password/verify-otp")
def verify_otp(request: schemas.OTPVerifyRequest, db: Session = Depends(get_db)):
    logger.info(f"OTP verification request for email: {request.email}")
    if crud.verify_otp(db, request.email, request.otp):
        logger.info(f"OTP verified successfully for: {request.email}")
        return {"message": "OTP verified"}
    logger.warning(f"Invalid or expired OTP for: {request.email}")
    raise HTTPException(status_code=400, detail="Invalid or expired OTP")

@app.post("/forgot-password/reset")
def reset_password(request: schemas.ResetPasswordRequest, db: Session = Depends(get_db)):
    logger.info(f"Password reset request for email: {request.email}")
    success = crud.reset_user_password(db, request.email, request.new_password)
    if success:
        logger.info(f"Password reset successful for: {request.email}")
        return {"message": "Password reset successful"}
    logger.warning(f"User not found for password reset: {request.email}")
    raise HTTPException(status_code=404, detail="User not found")
