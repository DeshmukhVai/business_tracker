"""BusinessPartner — links a User to a Business they can access.

The many-to-many join between users and businesses: a user can partner in
more than one business, and a business can have more than one partner.
Every partner has full access to that business's data; `role` only
decides who can manage the other partners and rename the business.
"""

from datetime import datetime

from extensions import db

ROLE_OWNER = "owner"
ROLE_PARTNER = "partner"
ROLES = (ROLE_OWNER, ROLE_PARTNER)


class BusinessPartner(db.Model):
    __tablename__ = "business_partners"
    __table_args__ = (
        db.UniqueConstraint("business_id", "user_id", name="uq_business_partner"),
    )

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=ROLE_PARTNER)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    business = db.relationship("Business", back_populates="partnerships")
    user = db.relationship("User", back_populates="partnerships")

    @property
    def is_owner(self):
        return self.role == ROLE_OWNER

    def __repr__(self):
        return f"<BusinessPartner business={self.business_id} user={self.user_id} role={self.role}>"
