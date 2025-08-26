
class DocumentNotFoundException(Exception):
    detail = 'Document not found'

class DocumentAlreadyExistsException(Exception):
    detail = 'Document already exists exception'