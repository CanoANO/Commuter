from sqlalchemy.orm import Session

class BaseGateway:
    def __init__(self, session: Session):
        self.session = session
