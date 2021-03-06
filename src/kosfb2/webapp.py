# -*- coding: utf-8 -*-



import cherrypy
import uuid
import jinja2
import os
import math
import time
import functools
import logging
import simplejson
import codecs
import kosfb2
from kosfb2.modules import FileUploader, DBManager, FileParser



print cherrypy.engine.state

tq = cherrypy.engine.bg_tasks_queue
dbm = DBManager(taskqueue = tq)


class Base(object):

    #Задаем место расположения файлов tpl для jinja2
    _cp_config = {
        'tools.jinja.loader': jinja2.PackageLoader (__package__, '__views__')
    }

    def __init__ (self):
        cherrypy.tools.jinja.env.filters ['dt'] = lambda value, format = '%d.%m.%Y %H:%M:%S': value.strftime (format) #@UndefinedVariable


class BookShelf(Base):

    def __init__(self):
        pass
    #----------------------------------------------------------------------------------------------------------------------------------------------------

    #Основные методы
    @cherrypy.expose
    @cherrypy.tools.jinja (template = 'book.tpl')
    def main(self):
        chs = cherrypy.session

        if chs.get('wasindex'):
            print "############## MAIN ###############"
            print "wasindex", chs.get('wasindex')
            print "find_chkd", chs.get('find_chkd')
            print "findkeyword", chs.get('findkeyword')
            print "group_chkd", chs.get('group_chkd')
            print "pagenumb", chs.get('pagenumb')
            print "pagebookcount", chs.get('pagebookcount')
            print "shortbooklist", chs.get('shortbooklist')
            print "fullbooklist", chs.get('fullbooklist')
            print "message", chs.get('message')

            mainparams = {'find_chkd': chs.get('find_chkd'),
                        'findkeyword': chs.get('findkeyword'),
                        'group_chkd': chs.get('group_chkd'),
                        'pagenumb' : chs.get('pagenumb'),
                        'pagebookcount' : chs.get('pagebookcount'),
                        'books' : chs.get('shortbooklist'),
                        'message' : chs.get('message')
                        }

            if chs.get('uploading'):
                uploadparams = {'uploading': 'True'}
                mainparams = dict(mainparams, **uploadparams)

            return mainparams
        else:
            raise cherrypy.HTTPRedirect("/index")


    #----------------------------------------------------------------------------------------------------------------------------------------------------

    @cherrypy.expose
    @cherrypy.tools.jinja (template = 'viewuploadlog.html')
    def viewuploadlog(self):
        chs = cherrypy.session
        return {'logfilename' : chs.get('uploaderlog')}

    @cherrypy.expose
    def getlog(self, tmpname):
        cherrypy.response.headers['Content-Type'] = 'application/json'
        u_tmpname = tmpname.encode("utf-8", "ignore")
        print u_tmpname

        disablerefresh = False

        with open(u_tmpname) as logfile:
            logtextlines = logfile.readlines()

            logtext = ""
            for textline in logtextlines:
                print "textline = ", textline
                if(textline != "END\n"):
                    logtext = "{}<br>{}".format(logtext, textline)
                else:
                    print "disablerefresh = True"
                    disablerefresh = True


#            laststring = logfile.readlines()[-1]
#            print "laststring = ", laststring
#            if laststring == "END":
#                disablerefresh = True
        return simplejson.dumps(dict(logtext = logtext, disablerefresh = disablerefresh))

    #----------------------------------------------------------------------------------------------------------------------------------------------------
    #Main page (Основная страница)
    @cherrypy.expose
    @cherrypy.tools.jinja (template = 'book.tpl')
    def index(self):
        chs = cherrypy.session

        chs['wasindex'] = True
        chs['find_chkd'], findtype, chs['findkeyword'] = self.init_findtype()
        chs['group_chkd'], groupetype = self.init_grouptype()
        chs['pagenumb'] = 0
        chs['pagebookcount'] = 20
        chs['fullbooklist'] = self.randbook(20)
        chs['shortbooklist'] = []
        chs['message'] = u"Первый запуск"

        self.showbook()
        #cherrypy.response.cookie['user_name'] = 'TurboGears User' #Пишем cookies. Пример
        #raise cherrypy.HTTPRedirect("/main")

    #Обработчик поисковых параметров
    @cherrypy.expose
    def findbook(self, *args, **kwargs):
        chs = cherrypy.session
        if chs.get('wasindex'):
            #Пробуем обработать параметры группировки из WEB-формы
            try:
                chs['grouptype'] = kwargs["grouptype"] #SQL inj
                #self.init_grouptype(type = self.grouptype)
            except (KeyError, ValueError):
                print "Error when get group parameters"
                self.init_grouptype()

            #Пробуем обработать параметры поиска из WEB-формы
            try:
                chs['findtype'] = kwargs["findtype"] #SQL inj
                chs['findkeyword'] = kwargs["findkeyword"] #SQL inj
                #self.init_findtype(type = self.findtype, text = self.findkeyword)
            except (KeyError, ValueError):
                print "Error when get find parameters"
                self.init_findtype()

            #Делаем запрос к БД и получаем список книг
            try:
                chs['fullbooklist'] = dbm.find_books(keyword = chs.get('findkeyword'),
                                                     findtype = chs.get('findtype'),
                                                     orderby = chs.get('grouptype'))
                chs['message'] = u"Найдено книг: %s" % (len(chs['fullbooklist']))
                #print chs['fullbooklist']
            except: #ErrorFindBook
                chs['fullbooklist'] = []
                #chs['message'] = "По данным условиям поиска книги не найдены"
                print "По данным условиям поиска книги не найдены"

            self.showbook()
        else:
            raise cherrypy.HTTPRedirect("/index")

    #Обработчик отображения нужных книг для выбранной страницы (выборка из всех найденных)
    @cherrypy.expose
    def showbook(self, *args, **kwargs):
        chs = cherrypy.session

        if chs.get('wasindex'):
            #Обновляем количество книг отображаемых на странице, если оно было изменено пользователем
            try:
                pagebookcount = int(kwargs["pagebookcount"]) #SQL inj
                chs['pagebookcount'] = pagebookcount
            except (KeyError, ValueError):
                pagebookcount = chs['pagebookcount']

            #Получаем информацию о переходе на другую страницу, если он был произведен пользователем
            try:
                pgnavstep = int(kwargs["pgnavstep"]) #SQL inj
            except (KeyError, ValueError):
                pgnavstep = 0

            #Получаем текущий номер страницы
            try:
                pagenumb = int(kwargs["pagenumb"]) - 1 #SQL inj
            except (KeyError, ValueError):
                pagenumb = chs['pagenumb']

            #Получаем список книг для отображения на текущей странице
            try:
                chs['pagenumb'] = 0
                chs['shortbooklist'] = []

                chs['pagenumb'], chs['shortbooklist'] = self.get_page_booklist(fullbooklist = chs.get('fullbooklist'),
                                                                           pagebookcount = pagebookcount,
                                                                           pagenumb = pagenumb,
                                                                           pgnavstep = pgnavstep)
                print chs['shortbooklist']
                #chs['message'] = u"Книги найдены"
            except: #ErrorGetShortBookList
                chs['pagenumb'] = 0
                chs['shortbooklist'] = []
                chs['message'] = u"По данным условиям поиска книги не найдены"

            #Вызываем главную страницу с параметрами отображения элементов интерфейса и с нужным списком книг
            raise cherrypy.HTTPRedirect("/main")
        else:
            raise cherrypy.HTTPRedirect("/index")

    #Добавление новых книг в библиотеку в фоне
    @cherrypy.expose
    def uploadbook(self, *args, **kwargs):
        chs = cherrypy.session
        errmessage = u"Книги не загружены. Что-то приключилось"

        if chs.get('wasindex'):
            cherrypy.response.timeout = 3600
            print "cherrypy.response.timeout = ", cherrypy.response.timeout

            try:

                uploadfile = cherrypy.request.params.get('uploadfiles') #SQL inj #Можно использовать встроенный в cherrypy метод получения параметров
                    #uploadfile = kwargs['uploadfiles'] #Можно получать параметры из запроса с помощью стандартных именованных параметров метода
                    #print "test uploadfile = ", uploadfile

                uploaderuid = str(uuid.uuid1())

                logfilepath = os.path.join('kosfb2', '__static__', 'logfiles', "%s.log" % (uploaderuid))
                chs['uploaderlog'] = logfilepath

                loggername = "".join(('upload_', uploaderuid))
                oneuploadhnd = logging.FileHandler(logfilepath)
                oneuploadhnd.setLevel(logging.INFO)

                oneuploadlogger = logging.getLogger(loggername)
                oneuploadlogger.addHandler(oneuploadhnd)
                oneuploadlogger.setLevel(logging.DEBUG)

                fu = FileUploader(uploadfolder = os.path.join('kosfb2', 'uploadedbook'),
                                  staticfolder = os.path.join('kosfb2', '__static__'),
                                  destfolder = os.path.join('kosfb2', '__static__', 'books'),
                                  loggername = loggername)

                uploader = functools.partial(fu.upload, doupload = True, files = uploadfile, tmpfoldername = uploaderuid)
                tq.put(uploader)

                chs['uploading'] = True
                chs['message'] = u"Книги загружаются в библиотеку"
                raise cherrypy.HTTPRedirect("/main")

            except (AttributeError, KeyError):
                chs['message'] = errmessage
                raise cherrypy.HTTPRedirect("/index")
        else:
            raise cherrypy.HTTPRedirect("/index")

    #----------------------------------------------------------------------------------------------------------------------------------------------------

    #Вспомогательные методы

    #----------------------------------------------------------------------------------------------------------------------------------------------------
    #Функция выдает случайный набор из книг, найденных в БД
    def randbook(self, *args, **kwargs):
        #count - кол-во книг которые необходимо выбрать из БД
        try:
            count = kwargs['count']
        except KeyError:
            count = 20

        return dbm.find_books(randbook = True, count = count)


    #Функция получает на входе результат поиска книг из БД
    #На выходе функция выдает массив из книг которые должны отображаться на текущей странице
    def get_page_booklist(self, fullbooklist = [], pagebookcount = 20, pagenumb = 0, pgnavstep = 0):
        #fullbooklist - полный результат поиска
        #pagebookcount - кол-во книг выводимых на страницу за один раз
        #pagenumb - порядковый номер страницы

        #start_pos = 0
        #end_pos = 0
        short_booklist = []

        #Вычисляем кол-во страниц, необходимое для отображения результатов поиска
        #pagebookcount - задается пользователем через web-форму
        if pagebookcount > 0:
            '''
            lenfullbooklist = len(fullbooklist)
            quotient = float(lenfullbooklist) / float(pagebookcount)
            roundedres = math.ceil(quotient)
            pagecount = int(roundedres)
            '''
            pagecount = int(math.ceil(float(len(fullbooklist)) / float(pagebookcount)))
        else:
            pagecount = 0

        #Получаем новый номер страницы на которую перешел пользователь
        print "!! pgnavstep ", pgnavstep

        if pagecount > 0:
            pagenumb = pagenumb + pgnavstep
            if pagenumb < 0:
                pagenumb = 0
            elif pagenumb > pagecount - 1:
                pagenumb = pagecount - 1
        else:
            pagenumb = 0

        #print "new page = ", pagenumb

        #Получаем номер первой книги на отображаемой странице
        start_pos = pagenumb * pagebookcount
        #Получаем номер последней книги на отображаемой странице
        end_pos = start_pos + pagebookcount

        #print "start_pos = ", start_pos
        #print "end_pos = ", end_pos

        #Берем из результа поиска книги для отображения на текущей странице
        for i in xrange(start_pos, end_pos):
            try:
                short_booklist.append(fullbooklist[i])
            except IndexError: #Если остался хвостик не кратный количеству книг выводимых на экране
                pass

        return (pagenumb, short_booklist)

    #Добавление новых книг в библиотеку после ошибки
    @cherrypy.expose
    def refindbook(self, *args, **kwargs):
        cherrypy.response.timeout = 3600
        print "cherrypy.response.timeout = ", cherrypy.response.timeout
        tmpfoldername = cherrypy.request.params.get('tmpfoldername') #Можно использовать встроенный в cherrypy метод получения параметров

        fu = FileUploader(uploadfolder = os.path.join('kosfb2', 'uploadedbook'),
                          staticfolder = os.path.join('kosfb2', '__static__'),
                          destfolder = os.path.join('kosfb2', '__static__', 'books'))

        fu.upload(find = True, tmpfoldername = tmpfoldername)

    #Добавление новых книг в библиотеку после ошибки
    @cherrypy.expose
    def reparsebook(self, *args, **kwargs):
        cherrypy.response.timeout = 3600
        print "cherrypy.response.timeout = ", cherrypy.response.timeout
        tmpfoldername = cherrypy.request.params.get('tmpfoldername') #Можно использовать встроенный в cherrypy метод получения параметров

        fu = FileUploader(uploadfolder = os.path.join('kosfb2', 'uploadedbook'),
                          staticfolder = os.path.join('kosfb2', '__static__'),
                          destfolder = os.path.join('kosfb2', '__static__', 'books'))

        fu.upload(parse = True, tmpfoldername = tmpfoldername)

    #Инициализация всех таблиц базы данных fb2data
    @cherrypy.expose
    def init_fb2_data (self):
        dbm.init_genre()
        dbm.init_db()

    #Инициализация таблицы жанров
    @cherrypy.expose
    def init_genre_table (self):
        dbm.init_genre()

    def init_findtype(self, type = 0, text = ''):
        find_chkd = []
        findtype = type #Тип поиска (где искать ключевое слово?) (Название 0, Автор 1, Серия 2, Издательская серия 3)
        findkeyword = text #Ключевое слово для поиска

        #Инициализируем массив с флагами о выборе "checked" для radio_buttons
        for i in xrange(4):
            find_chkd.append("")

        find_chkd[int(findtype)] = 'checked'
        return find_chkd, findtype, findkeyword

    def init_grouptype(self, type = 3):
        group_chkd = []
        grouptype = type #Тип группировки (где искать ключевое слово?) (Жанр 0, Серия 1, Издательская серия 2, Автор 3)
        #Инициализируем массив с флагами о выборе "checked" для radio_buttons
        for i in xrange(4):
            group_chkd.append('')

        group_chkd[int(grouptype)] = 'checked'
        return group_chkd, grouptype

    #----------------------------------------------------------------------------------------------------------------------------------------------------

    #Тестовые методы

    #----------------------------------------------------------------------------------------------------------------------------------------------------

    @cherrypy.expose
    def maintreadtest(self):
        print "THREAD MAIN"

    @cherrypy.expose
    def tread1test(self):
        dbm.testqueue()

    #Использование сессий
    @cherrypy.expose
    def session_test(self, *args, **kwargs):
        chs = cherrypy.session

        out = ''
        for key, value in kwargs.items():
            out += key + '=' + value + '\n'
            chs[key] = value
        print chs
        return out


    #----------------------------------------------------------------------------------------------------------------------------------------------------
    #Тестовый метод с JQuery
    @cherrypy.expose
    def jquery_test (self):
        #Будет чуть попозже
        pass


    #----------------------------------------------------------------------------------------------------------------------------------------------------
