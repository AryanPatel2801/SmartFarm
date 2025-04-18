from sqlalchemy.orm import Session
from . import models, schemas, security
import random
import logging
from datetime import datetime, timedelta

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_user_by_email(db: Session, email: str):
    try:
        return db.query(models.User).filter(models.User.email == email).first()
    except Exception as e:
        logger.error(f"Error getting user by email: {str(e)}")
        return None

def create_user(db: Session, user: schemas.UserCreate):
    try:
        hashed_password = security.get_password_hash(user.password)
        db_user = models.User(
            email=user.email,
            hashed_password=hashed_password,
            user_type=user.user_type.value,
            contact_number=user.contact_number,
            first_name=user.first_name,
            last_name=user.last_name
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user
    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        db.rollback()
        raise

def create_contact_us(db: Session, contact: schemas.ContactUsCreate):
    try:
        db_contact = models.ContactUs(
            name=contact.name,
            email=contact.email,
            phone_number=contact.phone_number,
            farm_size=contact.farm_size,
            primary_waste_type=contact.primary_waste_type,
            message=contact.message
        )
        db.add(db_contact)
        db.commit()
        db.refresh(db_contact)
        return db_contact
    except Exception as e:
        logger.error(f"Error creating contact: {str(e)}")
        db.rollback()
        raise

def create_otp(db: Session, email: str):
    try:
        # Generate OTP
        otp = str(random.randint(100000, 999999))
        logger.info(f"Generated OTP for {email}")

        # Create OTP record
        db_otp = models.PasswordResetOTP(
            email=email,
            otp=otp,
            created_at=datetime.utcnow()
        )
        db.add(db_otp)
        db.commit()
        db.refresh(db_otp)
        
        # Clean up old OTPs for this email
        old_otps = db.query(models.PasswordResetOTP).filter(
            models.PasswordResetOTP.email == email,
            models.PasswordResetOTP.id != db_otp.id
        ).all()
        for old_otp in old_otps:
            db.delete(old_otp)
        db.commit()
        
        return otp
    except Exception as e:
        logger.error(f"Error creating OTP: {str(e)}")
        db.rollback()
        raise

def verify_otp(db: Session, email: str, otp: str) -> bool:
    try:
        latest_otp = db.query(models.PasswordResetOTP).filter(
            models.PasswordResetOTP.email == email
        ).order_by(models.PasswordResetOTP.created_at.desc()).first()
        
        if latest_otp and latest_otp.otp == otp:
            time_diff = datetime.utcnow() - latest_otp.created_at
            is_valid = time_diff <= timedelta(minutes=10)
            logger.info(f"OTP verification for {email}: {'valid' if is_valid else 'expired'}")
            return is_valid
        
        logger.warning(f"Invalid OTP attempt for {email}")
        return False
    except Exception as e:
        logger.error(f"Error verifying OTP: {str(e)}")
        return False

def reset_user_password(db: Session, email: str, new_password: str):
    try:
        user = db.query(models.User).filter(models.User.email == email).first()
        if user:
            hashed = security.get_password_hash(new_password)
            user.hashed_password = hashed
            db.commit()
            logger.info(f"Password reset successful for {email}")
            return True
        logger.warning(f"Password reset attempted for non-existent user: {email}")
        return False
    except Exception as e:
        logger.error(f"Error resetting password: {str(e)}")
        db.rollback()
        return False