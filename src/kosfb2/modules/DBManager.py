# -*- coding: utf-8 -*-

from cherrybase import db #Нужно ли импортировать db чтобы работать с @cherrybase.db.use_db?
import uuid
import time
import functools
import os
import itertools
from fb2tools import mask_sql_injection as msj
from fb2tools import mask_sql_injection_approxi as msjp
import random
from fb2tools import encodeUTF8str as es
from fb2tools import decodeUTF8str as ds
from fb2tools import readaddspace as radd
from fb2tools import fileremover as frem
import psycopg2
from psycopg2.extensions import adapt
import logging

#print random.sample([1, 2, 3, 4, 5, 6], 3)

#pool_name = __package__
#cherrypy.engine.bg_tasks_queue = plugins.TasksQueue (cherrypy.engine)

pool_name = __name__.partition('.')[0]
print "pool_name = ", pool_name
print "DBManager - pool_name = ", pool_name
usedb = db.use_db(pool_name)

class DBManager:
    def __init__(self, *args, **kwargs):
        try:
            self.taskqueue = kwargs['taskqueue']
        except KeyError, ValueError:
            raise

        self.readylist = {}
        self.result = {}

        #self.logger = logging.getLogger(self.loggername)
        #self.result = []

    #----------------------------------------------------------------------------------------------------------------------------------------------------

    #Основные методы

    #----------------------------------------------------------------------------------------------------------------------------------------------------

    #Метод добавления задач очереди запросов к БД
    def execute_easy_task(self, query):
        taskuid = str(uuid.uuid1())
        return self.easy_task(sqlquery = query, taskuid = taskuid)


    #Метод добавления задач очереди запросов к БД
    def execute_task_in_queue(self, query):
        try_count = 0
        max_try_count = 100
        wait_time = 1

        taskuid = str(uuid.uuid1())
        task = self.create_queue_task(query, taskuid)

        #print "self.taskqueue = ", self.taskqueue

        try:
            self.taskqueue.put(task)
            while True:
                try:
                    #print self.result[taskuid]
                    result = self.result[taskuid] #Сохраняем результат выполения задачи
                    print "task_result = ", result
                    self.result = {i:self.result[i] for i in self.result if i != taskuid} #Удаляем результат выполнения задачи из словаря
                    return result
                except:
                    try_count = try_count + 1
                    if try_count > max_try_count:
                        print "Error, task timeout"
                        return []
                time.sleep (wait_time)
        except: # FIXME: Посмотреть какое исключение возникает в момент неудачноного добавления задачи в очередь
            print "Error, when task put to queue"
            return []

    '''
    #Генератор задачи - task содержащей запросы к БД котрую можно добавить в очередь с помощью - put_task_to_queue(task)
    def create_task(self, query, taskuid):
        def task(*args, **kwargs):
            return self.easy_task(sqlquery = query, taskuid = taskuid)
        return task
    '''

    #Генератор задачи - task содержащей запросы к БД котрую можно добавить в очередь с помощью - put_task_to_queue(task)
    def create_queue_task(self, query, taskuid):
        return functools.partial(self.easy_queue_task, sqlquery = query, taskuid = taskuid)

    @usedb
    def easy_task(self, db, *args, **kwargs):
        query = kwargs['sqlquery']
        taskuid = kwargs['taskuid']

        dbcursor = db.cursor()
        dbcursor.execute(query)
        try:
            result = dbcursor.fetchall()
            #print "Good result"
        except psycopg2.ProgrammingError:
            #print "Empty result"
            result = []

        dbcursor.close()
        return result

        #time.sleep (1)
        #self.readylist[taskuid] = True

    @usedb
    def easy_queue_task(self, db, *args, **kwargs):
        query = kwargs['sqlquery']
        taskuid = kwargs['taskuid']

        dbcursor = db.cursor()
        dbcursor.execute(query)
        try:
            self.result[taskuid] = dbcursor.fetchall()
            #print "Good result"
        except psycopg2.ProgrammingError:
            self.result[taskuid] = []
            #print "Empty result"
        dbcursor.close()

        #time.sleep (1)
        #self.readylist[taskuid] = True

    '''
    Использовать основные 2 метода класса можно примерно так:
    
    query = create_query_<имя конкретного генератора запроса>() ()
    task = create_task(query)
    put_task_to_queue(task)
    '''
    #----------------------------------------------------------------------------------------------------------------------------------------------------

    #Методы работы с книгами

    #----------------------------------------------------------------------------------------------------------------------------------------------------

        #Добавление новой книги

    #----------------------------------------------------------------------------------------------------------------------------------------------------

    #Запись информации по одной книге
    def add_book(self, Book, loggername):
        logger = logging.getLogger(loggername)

        newer_version = False
        exists = False
        iscorrect = False

        tq = self.execute_task_in_queue
        findrows = self.create_query_find_rows
        insertrow = self.create_query_insert_row
        updaterow = self.create_query_update_row
        et = self.execute_easy_task

        try:
            bookid = Book['ID']
            booktitle = Book['Title']
        except KeyError:
            print "Ошибка. Пустые мета-данные. В базу нечего добавлять"
            return False

        #Проверь есть ли книга с таким id в БД
        if(self.check_value_exist('book', 'fb2id', Book["ID"])):
            exists = True
            print "Запись в БД уже существует"
            logger.info("Запись в БД уже существует")
            #Проверь верcию книги, если книга уже есть в БД
            if(self.check_value_bigger('book', 'version', Book["Version"], 'fb2id', Book["ID"])):
                print "Добавляемая книга имеет более новую версию"
                logger.info("Добавляемая книга имеет более новую версию")
                newer_version = True
                self.delete_book(Book['ID'])
            else:
                print "Добавляемая книга имеет такую же версию или более раннюю"
                logger.info("Добавляемая книга имеет такую же версию или более раннюю")
                newer_version = False
                iscorrect = self.check_book_iscorrect(Book["ID"])
                if (not iscorrect):
                    #Удаляем существующую запись о книге из БД из всех связных таблиц
                    print "Ошибка. Запись в БД по книге не корректна. Будет удален файл и мета-данные"
                    logger.info("Ошибка. Запись в БД по книге не корректна. Будет удален файл и мета-данные")
                    self.delete_book(Book['ID'])
                    exists = False
        else:
            exists = False

        #Добавь мета-данные книги в БД, если ее нет в базе, или книга имеет более новую версию чем существующая в БД
        if (not exists) or newer_version:
            #Формируем запрос к БД

            '''
            #------------------------------------------  
            
            Используемые таблицы
            
            book
                bookauthor
            author
            genre
                bookgenre
            sequence
                booksequence
            pubsequence
                bookpubsequence
            publisher
            lang
             
            #------------------------------------------       
            
            Структура мета-данных книги
            
            #------------------------------------------
            
            'ID' 
                Проверяем существет ли такая книга в БД
            
            'Version'
                Проверяем версию книги
                
            Добавляем простые поля книги в таблицу book 
            'ID' в fb2id
            'Version' в version
            'Title' в title
            'Annotation' в annotation
            'CoverFile' в coverfile
            'CoverExist' в coverexist
            'ZipFile' в zipfile
                 Просто записываем значения в таблицу book
                 
            '''
            try:
                book_uid = et(insertrow(table = 'book',
                                        fields = ['fb2id',
                                                  'iscorrect',
                                                  'version',
                                                  'encoding',
                                                  'title',
                                                  'coverfile',
                                                  'coverexist',
                                                  'zipfile'],
                                        values = [Book["ID"],
                                                  False,
                                                  Book["Version"],
                                                  Book["Encoding"],
                                                  Book["Title"],
                                                  Book["CoverFile"],
                                                  Book["CoverExist"],
                                                  Book["ZipFile"]]))[0][0]
            except KeyError:
                print "Ошибка. Не удалось добавить новую запись в таблицу book"
                return False

            #Пробуем получить описание книги
            try:
                annotation = Book["Annotation"]
                et(updaterow(table = 'book',
                         updatefields = ['annotation'],
                         values = [annotation]),
                         keyfield = 'uid',
                         keyword = book_uid)
            except KeyError:
                print "Ошибка. Не удалось получить описание книги"

            '''
                 
            Получаем uid новой книги из таблицы book по добавленному fb2id 
                
            #------------------------------------------
            
            'Lang' 
                Находим uid языка из таблицы language
                Ищем uid по полям altercode1, altercode2, langcode
                Записываем в таблицу book
            '''

            try:
                lang = Book['Lang']

                lang_uid = et(findrows(keyword = lang,
                                       showfields = ['uid'],
                                       keyfield = 'langcode',
                                       table = 'language'))

                et(updaterow(table = 'book',
                             updatefields = ['langid'],
                             values = [lang_uid[0][0]],
                             keyfield = 'uid',
                             keyword = book_uid))
            except KeyError:
                print "Ошибка. Не удалось получить язык книги"
            '''
            #------------------------------------------
            
            'Sequences'
                'Name' Проверяем есть ли такая серия в таблице sequence
                
                Добавляем новую серию в таблицу sequence (если такой еще не было) или сразу берем uid из таблицы sequence
                Добавляем запись в таблицу booksequence
            '''

            try:
                sequences = Book['Sequences']

                for sequence in Book['Sequences']:
                    sequence_uid = et(findrows(keyword = sequence['Name'],
                                      showfields = ['uid'],
                                      keyfield = 'name',
                                      table = 'sequence'))

                    #Если не нашли серию в БД
                    if len(sequence_uid) <= 0:
                        sequence_uid = et(insertrow(table = 'sequence',
                                                         fields = ['name'],
                                                         values = [sequence['Name']]))

                    #Добавляемсвязь серии и книги
                    et(insertrow(table = 'booksequence',
                                      fields = ['bookid',
                                                'sequenceid',
                                                'volume'],
                                      values = [book_uid,
                                                sequence_uid[0][0],
                                                sequence['Volume']]))
            except KeyError:
                print "Ошибка. Не удалось получить данные по сериям книги"
            '''
            #------------------------------------------  
            
            'Publisher'
                Проверяем есть ли такой издатель в таблице publisher, если нет то добавляем нового издателя
                Получаем uid издателя
            '''
#            query = findrows(keyword = Book['Publisher'],
#                             showfields = ['uid'],
#                             table = 'publisher',
#                             keyfield = 'name')
#            publisher_uid = et(query)

            #Пробуем получить описание книги
            try:
                publisher = Book["Publisher"]
                publisher_uid = et(findrows(keyword = publisher,
                                         showfields = ['uid'],
                                         keyfield = 'name',
                                         table = 'publisher'))

                #Если не нашли издателя в БД
                if len(publisher_uid) <= 0:
                    publisher_uid = et(insertrow(table = 'publisher',
                                                 fields = ['name'],
                                                 values = [publisher]))

                et(updaterow(table = 'book',
                             updatefields = ['publisherid'],
                             values = [publisher_uid[0][0]],
                             keyfield = 'uid',
                             keyword = book_uid))
            except KeyError:
                print "Ошибка. Не удалось получить название издателя книги"



            ''' 
            #------------------------------------------
            
            'PubSequences'
                Добавляем новую серию в таблицу pubsequence (если такой еще не было) или сразу берем uid из таблицы pubsequence
                Добавляем запись в bookpubsequence
            
                'Name' Проверяем есть ли такая серия в таблице sequence
                
                Указываем в таблице pubsequence publisherid = uid издателя из таблицы publisher
                
            '''
            try:
                sequences = Book['PubSequences']

                for pubsequence in Book['PubSequences']:
                    pubsequence_uid = et(findrows(keyword = pubsequence['Name'],
                                      showfields = ['uid'],
                                      keyfield = 'name',
                                      table = 'pubsequence'))

                    #Если не нашли серию в БД
                    if len(pubsequence_uid) <= 0:
                        pubsequence_uid = et(insertrow(table = 'pubsequence',
                                                       fields = ['name'],
                                                       values = [pubsequence['Name']]))

                    #Добавляемсвязь серии и книги
                    et(insertrow(table = 'bookpubsequence',
                                fields = ['bookid',
                                          'sequenceid',
                                        'volume'],
                                values = [book_uid,
                                          pubsequence_uid[0][0],
                                          pubsequence['Volume']]))
            except KeyError:
                print "Ошибка. Не удалось получить данные по издательским сериям книги"
            '''

            #------------------------------------------
            
            'Genres'
                Получаем список uid'ов из таблицы genre по полученным genrecode
                Добавляем записи для каждого uid в таблицу bookgenre
            '''

            try:
                genres = Book['Genres']
                print "Genres = ", genres
                for genre in genres:
                    try:
                        genre_uid = et(findrows(keyword = genre,
                                                showfields = ['uid'],
                                                keyfield = 'code',
                                                table = 'genre'))[0][0]
                    except:
                        print "В книге указан не известный жанр: ", genre
                        genre_uid = et(insertrow(table = 'genre',
                                                 fields = ['code', 'name'],
                                                 values = [genre, 'Неизвестный жанр']))[0][0]
                    finally:
                        et(insertrow(table = 'bookgenre',
                                     fields = ['bookid',
                                               'genreid'],
                                     values = [book_uid,
                                               genre_uid]))
            except KeyError:
                print "Ошибка. Не удалось получить данные по жанрам книги"

            '''
            #------------------------------------------
            
            'Authors'
                'FirstName'
                'LastName'
                'MiddleName'
                'NickName'
                
                Проверяем есть ли авторы с такими firstname и lastname и middlename и nickname в таблице author
                Если совпадение есть то берем uid'ы авторов из таблицы author
                    Если есть совпадение но одно из полей в таблице author не заполнено, дополняем запись в таблице author полученными значениями
                Если совпадений нет то создаем новых авторов в таблице author и получаем их uid'ы
                Добавляем записи в таблицу bookauthor
                
            '''

            try:
                authors = Book['Authors']
                for author in authors:
                    try:
                        last = author['LastName']
                    except:
                        last = ""
                    try:
                        first = author['FirstName']
                    except:
                        first = ""
                    try:
                        middle = author['MiddleName']
                    except:
                        middle = ""
                    try:
                        nick = author['NickName']
                    except:
                        nick = ""

                    author_uid = et(self.create_query_find_authors(lastname = last, firstname = first, middlename = middle, nickname = nick))

                    if len(author_uid) <= 0:
                        author_uid = et(insertrow(table = 'author',
                                                  fields = ['lastname',
                                                            'firstname',
                                                            'middlename',
                                                            'nickname'],
                                                  values = [last,
                                                            first,
                                                            middle,
                                                            nick]))

                    et(insertrow(table = 'bookauthor',
                                 fields = ['bookid',
                                           'authorid'],
                                 values = [book_uid,
                                           author_uid[0][0]]))
            except KeyError:
                print "Ошибка. Авторы книги не найдены"


            et(updaterow(table = 'book',
                         updatefields = ['iscorrect'],
                         values = [True],
                         keyfield = 'uid',
                         keyword = book_uid))
            return True
        else:
            return False
        #------------------------------------------

        #cur.execute("INSERT INTO book (apoint) VALUES (%s)",
        #    ...             (Point(1.23, 4.56),))
        #return "book was added to"


    #----------------------------------------------------------------------------------------------------------------------------------------------------

        #Поиск книг по заданным критериям

    #----------------------------------------------------------------------------------------------------------------------------------------------------

    #Поиск книг
    def find_books(self, *args, **kwargs):
        tq = self.execute_task_in_queue
        et = self.execute_easy_task

        #Если orderfield не передано или пусто то используем сортировку по алфавиту
        try:
            randbook = bool(kwargs['randbook']) #
            count = int(kwargs['count'])
        except KeyError:
            randbook = False

        wheretitlestring = " "
        whereauthorstring = " "
        wheregenrestring = " "
        whereseqstring = " "
        wherepubseqstring = " "
        wherepubstring = " "

        try:
            keyword = es(ds(kwargs['keyword'])) #Ключевое слово для поиска
            findtype = int(kwargs['findtype']) #Тип поиска

            if findtype == 0:
                wheretitlestring = "WHERE B.title like {0}".format(msjp(keyword))
            elif findtype == 1:
                whereauthorstring = "WHERE A.firstname like {0} OR A.lastname like {0} OR A.middlename like {0} OR A.nickname like {0}".format(msjp(keyword))
            elif findtype == 2:
                whereseqstring = "WHERE S.name like {0}".format(msjp(keyword))
            elif findtype == 3:
                wherepubseqstring = "WHERE PS.name like {0}".format(msjp(keyword))
        except KeyError:
            pass

        orderbysrting = " "

        try:
            orderby = int(kwargs['orderby']) #Тип сортировки

            if orderby == 0:
                orderbysrting = "ORDER BY gname"
            elif orderby == 1:
                orderbysrting = "ORDER BY sname"
            elif orderby == 2:
                orderbysrting = "ORDER BY psname"
            elif orderby == 3:
                orderbysrting = "ORDER BY lastname"
        except KeyError:
            pass

        sqlsource = os.path.join(pool_name, "sql/create_query_find_books.sql")

        query = ""
        with open(sqlsource, 'r') as fquery:
            query = fquery.read()

        #print type(query)

        query = query.replace('WHERETITLESTRING', wheretitlestring)
        query = query.replace('WHEREAUTHORSTRING', whereauthorstring)
        query = query.replace('WHEREGENRESTRING', wheregenrestring)
        query = query.replace('WHERESEQSTRING', whereseqstring)
        query = query.replace('WHEREPUBSEQSTRING', wherepubseqstring)
        query = query.replace('WHEREPUBSTRING', wherepubstring)

        query = query.replace('ORDERBYSTRING', orderbysrting)

        #print query

        '''
        for line in content:
            line = line.replace("WHERESTRING", wherestring).replace("ORDERBYSTRING", orderbysrting)
            query = "%s%s" % query, line
            print line
        '''

        #Дополняем раздел WHERE
        #query.replace("WHERESTRING", wherestring)
        #Дополняем раздел OREDER BY
        #query.replace("ORDERBYSTRING", orderbysrting)

        #print query

        books_array = et(query)

        #Если включен режим случайной выборки, то отбираем n книг из всей выборки
        if randbook:
            if count > len(books_array):
                count = len(books_array)
            books_array = [ books_array[i] for i in sorted(random.sample(xrange(len(books_array)), count)) ]

        books_dict_array = []

        #Если найдена хотя бы одна книга
        if len(books_array) > 0:
            #Разбираем полученный результат в словарь для удобного использования
            for book in books_array:
                book_dict = {}

                authors_array = []
                #authors_string = ""

                genres_array = []
                #genres_string = ""

                sequences_array = []
                #sequences_string = ""

                pubsequences_array = []
                #pubsequences_string = ""


                book_dict['CoverFile'] = ds(book['coverfile'])
                print "Обложка книги: ", book_dict['CoverFile']
                book_dict['UID'] = book['uid']
                print "UID книги: ", book_dict['UID']
                book_dict['Title'] = ds(book['title'])
                print "Название книги: ", book_dict['Title']

                try:
                    for i in xrange(len(book['lastname'])):

                        ilastname = radd(book['lastname'][i])
                        ifirstname = radd(book['firstname'][i])
                        imiddlename = radd(book['middlename'][i])
                        inickname = radd(book['nickname'][i])

                        author_fullname = ""
                        author_fullname = "%s%s%s%s" % (ilastname, ifirstname, imiddlename, inickname)
                        #author_fullname = book['fullauthorname'][i]
                        print "author_fullname = ", author_fullname
                        if author_fullname != "":
                            author_fullname = author_fullname[:-1]
                            authors_array.append(author_fullname)

                    book_dict['Authors'] = authors_array
                    print "Авторы: ", book_dict['Authors']
                except KeyError:
                    pass

                try:
                    for i in xrange(len(book['genres'])):
                        if book['genres'][i]:
                            igenre = ds(book['genres'][i])
                            if igenre != "":
                                genres_array.append(igenre)
                        #genres_array = "%s%s; " % (genres_string, book['genres'][i])

                    book_dict['Genres'] = genres_array
                    print "Жанры: ", book_dict['Genres']
                except KeyError:
                    pass

                try:
                    book_dict['Publisher'] = book['publisher']
                except KeyError:
                    book_dict['Publisher'] = ""
                print "Издатель: ", book_dict['Publisher']


                book_dict['Sequences'] = self.sequence_parser(book['sequences'], book['svolume'])
                print "Cерии: ", book_dict['Sequences']


                book_dict['PubSequences'] = self.sequence_parser(book['pubsequences'], book['psvolume'])
                print "Издательские серии: ", book_dict['PubSequences']

                try:
                    book_dict['ZipFile'] = ds(book['zipfile'])
                except KeyError:
                    book_dict['ZipFile'] = ""
                print "Архив книги: ", book_dict['ZipFile']

                print "--------------------------------------------------------------------------------------"
                books_dict_array.append(book_dict)
        #print books_dict_array
        return books_dict_array

    #Функция для получения полного названия серий с томом книги
    def sequence_parser(self, sequence, volume):
        sequences_array = []
        #try:
        for i in xrange(len(sequence)):
            pubsequence_fullname = ""
            sequencename = ""
            volumename = ""

            if sequence[i]:
                sequencename = sequence[i]

                if volume[i]:
                    volumename = str(volume[i])

                    if(sequencename != "" and volumename != ""):
                        connector = ", Том: "
                        sequence_fullname = u"{0}{1}{2}".format(ds(es(sequencename)), ds(es(connector)), ds(es(volumename)))

                    sequences_array.append(sequence_fullname)
        return sequences_array
        #except:
        #    return []

    #Каскадное удаление записей о книге и файлов
    @usedb
    def delete_book(self, db, fb2id):
        tq = self.execute_task_in_queue
        et = self.execute_easy_task

        #findrows = self.create_query_find_rows

        et(self.create_query_delete_rows(table = 'book', field = 'fb2id', values = [fb2id]))

        archfile = os.path.join("kosfb2", "__static__", "books", "%s%s" % (fb2id, ".zip"))
        jpgfile = os.path.join("kosfb2", "__static__", "books", "%s%s" % (fb2id, ".jpg"))
        pngfile = os.path.join("kosfb2", "__static__", "books", "%s%s" % (fb2id, ".png"))

        frem(jpgfile)
        frem(pngfile)
        frem(archfile)

        '''
        result = tq(findrows(keyword = fb2id,
                                showfields = ['coverexist', 'coverfile', 'zipfile'],
                                keyfield = 'fb2id',
                                table = 'book'))

        print "delete book result ", result

        time.sleep(5)

        try:
            delbook = result[0]
        except IndexError:
            delbook = result

        
        '''

        print "Мета-данные и файлы книги удалены"

    #----------------------------------------------------------------------------------------------------------------------------------------------------



    #----------------------------------------------------------------------------------------------------------------------------------------------------

    #Вспомогательные методы

    #----------------------------------------------------------------------------------------------------------------------------------------------------

    def sqlv(self, valuearray):
        str_values = [str(msj(val)) for val in valuearray]
        return ", ".join(str_values)   #Конвертируем все значения в строки

    #Генератор SQL-запроса для поиска подстроки keyword в поле field в таблице table c необязательным упорядочиванием по orderfield
    def create_query_find_authors(self, *args, **kwargs):
        try:
            lastname = msjp(kwargs['lastname'])
        except ValueError:
            lastname = msjp("")
        try:
            firstname = msjp(kwargs['firstname'])
        except ValueError:
            firstname = msjp("")
        try:
            middlename = msjp(kwargs['middlename'])
        except ValueError:
            middlename = msjp("")
        try:
            nickname = msjp(kwargs['nickname'])
        except ValueError:
            nickname = msjp("")

        select_query = "SELECT uid FROM author WHERE lastname LIKE {0} AND firstname LIKE {1} AND middlename LIKE {2} AND nickname LIKE {3}".format(lastname, firstname, middlename, nickname)
        #print "select_query = ", select_query

        return select_query

    #Проверяем правильно ли была добавлена уже существующая книга
    #Правильно?
    @usedb
    def check_book_iscorrect(self, db, fb2id):
        select_query = "SELECT iscorrect from book WHERE fb2id = {0};".format(msj(fb2id))
        #print "select_query = ", select_query
        select_result = db.select_value(select_query)
        #print select_result
        return bool(select_result)

    #Проверяем есть ли значение value поля field в указанной таблице table
    #Существует?
    @usedb
    def check_value_exist(self, db, table, field, value):
        select_query = "SELECT count(*) from {0} WHERE {1} = {2};".format(table, field, msj(value))
        #print "select_query = ", select_query
        select_result = db.select_value(select_query)

        #print "select_result = ", select_result

        if int(select_result) > 0:
            return True
        else:
            return False

    #Проверяем больше ли значение value чем? то которое уже записано в таблицу table в записи с полем id_name = id_value
    #Больше?
    @usedb
    def check_value_bigger(self, db, table, field, value, id_name, id_value):
        select_query = "SELECT {0} from {1} WHERE {2} = {3};".format(field, table, id_name, msj(id_value))
        #print "select_query = ", select_query
        select_result = db.select_value(select_query)
        #print "select_result = ", select_result
        if float(value) > float(select_result):
            return True
        else:
            return False

    #Генератор SQL-запроса для поиска подстроки keyword в поле field в таблице table c необязательным упорядочиванием по orderfield
    def create_query_find_rows(self, *args, **kwargs):
        #Если orderfield не передано или пусто то используем сортировку по алфавиту

        try:
            keyword = msjp(kwargs['keyword']) #Ключевое слово для поиска
            showfields = kwargs['showfields'] #Поля таблицы которые нужно вывести в поиске
            keyfield = kwargs['keyfield'] #Поле таблицы по которому необходимо производить поиск
            table = kwargs['table'] #Имя таблицы в которой будет производиться поиск
        except KeyError:
            raise

        showfields = ', '.join(showfields)

        try:
            orderfield = kwargs['orderfield']
            orderfield = "ORDER BY {0}".format(msj(orderfield))
        except:
            orderfield = " "

        select_query = "SELECT {0} FROM {1} WHERE {2} LIKE {3} {4};".format(showfields, table, keyfield, keyword, orderfield)
        #print "select_query = ", select_query

        return select_query

    #Генератор SQL-запроса для добавления одной строки с полями fields и значениями values  в таблицу table
    def create_query_delete_rows(self, *args, **kwargs):
        try:
            table = kwargs['table']                 #Имя таблицы
            field = kwargs['field']                 #Поля которым необходимо присвоить значения
            values = self.sqlv(kwargs['values'])
        except KeyError:
            raise

        query_str = "DELETE FROM {0} WHERE {1} IN ({2});".format(table, field, values)
        #print "query_str = ", query_str

        return query_str

    #Генератор SQL-запроса для добавления одной строки с полями fields и значениями values  в таблицу table
    def create_query_insert_row(self, *args, **kwargs):
        try:
            table = kwargs['table']                 #Имя таблицы
            fields = ', '.join(kwargs['fields'])    #Поля которым необходимо присвоить значения
            values = self.sqlv(kwargs['values'])
        except KeyError:
            raise

        select_query = str("INSERT INTO {0} ({1}) VALUES ({2}) RETURNING uid;".format(table,
                                                                                      fields,
                                                                                      values))
        #print "select_query = ", select_query

        return select_query

    #Генератор SQL-запроса для добавления одной строки с полcreate_query_delete_rowsями fields и значениями values  в таблицу table
    def create_query_update_row(self, *args, **kwargs):

        try:
            table = kwargs['table']                 #Имя таблицы
            updatefields = kwargs['updatefields']   #Поля которым необходимо присвоить значения
            values = kwargs['values']    #Новые значения
            keyfield = kwargs['keyfield'] #Поле таблицы по которому необходимо производить поиск
            keyword = msj(kwargs['keyword']) #Ключевое слово для поиска
        except KeyError:
            raise

        setvalues_array = []
        for f, v in itertools.izip(updatefields, values):
            setvalues_array.append("{0} = {1}".format(f, msj(v)))

        setvalues = ', '.join(setvalues_array)

        select_query = "UPDATE {0} SET {1} WHERE {2} = {3};".format(table, setvalues, keyfield, keyword)

        #print "select_query = ", select_query

        return select_query

    #Создаем все таблицы для проекта kosfb2
    @usedb
    def init_db(self, db):
        #Создаем БД
        #Создаем пользователя
        #Задаем права доступа пользователя

        sqlsource = os.path.join(pool_name, "sql/init_fb2data.sql")
        #print sqlsource

        with open(sqlsource, 'r') as fquery:
            myquery = fquery.read()
            #print "query_str = ", myquery

        mycursor = db.cursor()
        myquery = myquery
        mycursor.execute(myquery)

        print u"Таблицы созданы"

    #Создаем все таблицы для проекта kosfb2
    @usedb
    def init_genre(self, db):
        #Создаем БД
        #Создаем пользователя
        #Задаем права доступа пользователя

        sqlsource = os.path.join(pool_name, "sql/init_genre_table.sql")
        #print sqlsource

        with open(sqlsource, 'r') as fquery:
            myquery = fquery.read()
            print "query_str = ", myquery

        mycursor = db.cursor()
        myquery = myquery
        mycursor.execute(myquery)

        print u"Таблицы созданы"

    #----------------------------------------------------------------------------------------------------------------------------------------------------

    #Тестовые методы

    #----------------------------------------------------------------------------------------------------------------------------------------------------

    #Запиши всю информацию по книгам (книги)
    def insert_several_items(self, items = []):
        #Запуск insert_item(myitems[i]) по списку переданных объектов
        #for item in myitems:
            #insert_one_book(item)
        pass



    #Тестовый метод. Проверка connection usedb декоратора
    @usedb
    def testdb(self, db, *args, **kwargs):
        print db


    def testqueue(self):
        self.taskqueue.put(self.threadtask)

    def threadtask(self):
        while True:
            time.sleep(10)
            print "THREAD 1"
