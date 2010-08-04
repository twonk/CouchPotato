import sqlalchemy as sql_
import sqlalchemy.orm as sql_orm_
import sqlalchemy.types as sql_t_
from app.core import getLogger
import _tables
import os
from sqlalchemy.schema import ForeignKey
import shutil
from imaplib import Time2Internaldate
import time
from app.core.environment import Environment as env_
import traceback


log = getLogger(__name__)
class Database(object):
    typeLookup = {
         'i' :   sql_t_.Integer,
         's' :   sql_t_.Unicode,
         'b' :   sql_t_.Boolean,
         't' :   sql_t_.UnicodeText
    }
    '''
    Provides a database abstraction
    '''
    def __init__(self, file):
        '''
        Constructor
        '''
        self.file = file
        self.engine = sql_.create_engine('sqlite:///%s' % file)
        self.metadata = sql_.schema.MetaData(self.engine)
        self.session = sql_orm_.scoped_session(
                sql_orm_.sessionmaker(bind = self.engine, autocommit = True)
        )

        env_._db = self
        log.info('Loading Database...')
        doUpgrade = os.path.isfile(self.file)
        _tables.bootstrap(self)
        session = self.createSession()
        if doUpgrade:
            info = session.query(_tables.PluginsTable).filter_by(name = u'core', type_id = 1).one()
            self.upgradeDatabase(info, _tables.latestVersion, _tables)
        else:
            type = _tables.PluginTypesTable('core')
            session.add(type)
            session.flush()
            type_id = type.id
            session.add(_tables.PluginsTable('core', type_id, _tables.latestVersion))
            session.flush()

        """
        

        metadata.create_all()

        if doUpgrade:
            #upgradeDb()
            pass
        else:
            for nr in range(1, latestDatabaseVersion + 1):
                Session.add(DbVersion(nr))
                Session.flush()
        log.info('Database loaded')
        """

    def createSession(self):
        return self.session()

    def getTable(self, name, columns, constraints = None):
        constraints = constraints or [] #protected from persistent default argument
        columns = [self.getColumn(*args_ , **kwargs_) for args_, kwargs_ in columns]
        columns.extend(constraints)
        return sql_.schema.Table(
            name,
            self.metadata,
            *columns
        )

    def getAutoIdTable(self, name, columns, constraints = None):
        constraints = constraints or [] #protected from persistent default argument
        columns.insert(0, (('id', 'i'), {'primary_key' : True}))
        return self.getTable(
            name, columns
        )

    def getColumn(self, *args, **kwargs):
        args = [arg for arg in args]
        if Database.typeLookup.has_key(args[1]):
            args[1] = Database.typeLookup[args[1]]

        #foreign key handling
        if args.__len__() == 3:
            if isinstance(args[2], str):
                args[2] = ForeignKey(args[2])
            elif isinstance(args[2], tuple):
                args[2] = ForeignKey(args[2][0], **args[2][1])

        return sql_.schema.Column(
            *args,
            ** kwargs
        )

    def create(self):
        self.metadata.create_all()

    def getDbVersion(self):
        return env_.get('coreInfo')


    def upgradeDatabase(self, info, latest_version, scope):
        self.metadata.create_all()
        current_version = info.version
        session = self.createSession()
        if current_version < latest_version:
            log.info('Upgrading database for ' + info.name)
            shutil.copy(self.file, self.file + '_' + time.strftime("%Y-%m-%d_%H-%M-%S") + '.db')
            for tempVersion in range(current_version + 1, latest_version + 1):
                methodName = 'migrateToVersion' + str(tempVersion)
                if hasattr(scope, methodName):
                    method = getattr(scope, methodName)
                    try:
                        method()
                        info.version += 1
                        session.add(info)
                        session.flush()
                    except:
                        log.info('Error while updating ' + str(info.name) + ":\n" + traceback.format_exc())
                        return
                else:
                    log.info('Error while updating ' + str(info.name)
                             + ': method ' + methodName
                             + ' not found.')
                    return
            #for end
            log.info('Updated ' + str(info.name) + ', is now at version ' + str(info.version))




