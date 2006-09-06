/*
 *  Copyright (c) 2003-2006 Open Source Applications Foundation
 *
 *  Licensed under the Apache License, Version 2.0 (the "License");
 *  you may not use this file except in compliance with the License.
 *  You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 *  Unless required by applicable law or agreed to in writing, software
 *  distributed under the License is distributed on an "AS IS" BASIS,
 *  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 *  See the License for the specific language governing permissions and
 *  limitations under the License.
 */


#include <Python.h>
#include "structmember.h"

#include "c.h"

static void t_kind_dealloc(t_kind *self);
static int t_kind_traverse(t_kind *self, visitproc visit, void *arg);
static int t_kind_clear(t_kind *self);
static PyObject *t_kind_new(PyTypeObject *type, PyObject *args, PyObject *kwds);
static int t_kind_init(t_kind *self, PyObject *args, PyObject *kwds);

static PyObject *t_kind_getAttribute(t_kind *self, PyObject *args);

static PyObject *t_kind_getMonitorSchema(t_kind *self, void *data);
static int t_kind_setMonitorSchema(t_kind *self, PyObject *arg, void *data);
static PyObject *t_kind_getAttributesCached(t_kind *self, void *data);
static int t_kind_setAttributesCached(t_kind *self, PyObject *arg, void *data);
static PyObject *t_kind_getSuperKindsCached(t_kind *self, void *data);
static int t_kind_setSuperKindsCached(t_kind *self, PyObject *arg, void *data);
static PyObject *t_kind_getDescriptorsInstalled(t_kind *self, void *data);
static int t_kind_setDescriptorsInstalled(t_kind *self, PyObject *arg,
                                          void *data);
static PyObject *t_kind_getDescriptorsInstalling(t_kind *self, void *data);
static int t_kind_setDescriptorsInstalling(t_kind *self, PyObject *arg,
                                          void *data);


static PyMemberDef t_kind_members[] = {
    { "descriptors", T_OBJECT, offsetof(t_kind, descriptors), 0,
      "attribute descriptors" },
    { NULL, 0, 0, 0, NULL }
};

static PyMethodDef t_kind_methods[] = {
    { "getAttribute", (PyCFunction) t_kind_getAttribute, METH_VARARGS, "" },
    { NULL, NULL, 0, NULL }
};

static PyGetSetDef t_kind_properties[] = {
    { "monitorSchema",
      (getter) t_kind_getMonitorSchema,
      (setter) t_kind_setMonitorSchema,
      NULL, NULL },
    { "attributesCached",
      (getter) t_kind_getAttributesCached,
      (setter) t_kind_setAttributesCached,
      NULL, NULL },
    { "superKindsCached",
      (getter) t_kind_getSuperKindsCached,
      (setter) t_kind_setSuperKindsCached,
      NULL, NULL },
    { "descriptorsInstalled",
      (getter) t_kind_getDescriptorsInstalled,
      (setter) t_kind_setDescriptorsInstalled,
      NULL, NULL },
    { "descriptorsInstalling",
      (getter) t_kind_getDescriptorsInstalling,
      (setter) t_kind_setDescriptorsInstalling,
      NULL, NULL },
    { NULL, NULL, NULL, NULL, NULL }
};


static PyTypeObject KindType = {
    PyObject_HEAD_INIT(NULL)
    0,                                                   /* ob_size */
    "chandlerdb.schema.c.CKind",                         /* tp_name */
    sizeof(t_kind),                                      /* tp_basicsize */
    0,                                                   /* tp_itemsize */
    (destructor)t_kind_dealloc,                          /* tp_dealloc */
    0,                                                   /* tp_print */
    0,                                                   /* tp_getattr */
    0,                                                   /* tp_setattr */
    0,                                                   /* tp_compare */
    0,                                                   /* tp_repr */
    0,                                                   /* tp_as_number */
    0,                                                   /* tp_as_sequence */
    0,                                                   /* tp_as_mapping */
    0,                                                   /* tp_hash  */
    0,                                                   /* tp_call */
    0,                                                   /* tp_str */
    0,                                                   /* tp_getattro */
    0,                                                   /* tp_setattro */
    0,                                                   /* tp_as_buffer */
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,            /* tp_flags */
    "C Kind type",                                       /* tp_doc */
    (traverseproc)t_kind_traverse,                       /* tp_traverse */
    (inquiry)t_kind_clear,                               /* tp_clear */
    0,                                                   /* tp_richcompare */
    0,                                                   /* tp_weaklistoffset */
    0,                                                   /* tp_iter */
    0,                                                   /* tp_iternext */
    t_kind_methods,                                      /* tp_methods */
    t_kind_members,                                      /* tp_members */
    t_kind_properties,                                   /* tp_getset */
    0,                                                   /* tp_base */
    0,                                                   /* tp_dict */
    0,                                                   /* tp_descr_get */
    0,                                                   /* tp_descr_set */
    0,                                                   /* tp_dictoffset */
    (initproc)t_kind_init,                               /* tp_init */
    0,                                                   /* tp_alloc */
    (newfunc)t_kind_new,                                 /* tp_new */
};


static void t_kind_dealloc(t_kind *self)
{
    t_kind_clear(self);
    self->ob_type->tp_free((PyObject *) self);
}

static int t_kind_traverse(t_kind *self, visitproc visit, void *arg)
{
    Py_VISIT((PyObject *) self->kind);
    Py_VISIT(self->descriptors);
    return 0;
}

static int t_kind_clear(t_kind *self)
{
    Py_CLEAR(self->kind);
    Py_CLEAR(self->descriptors);
    return 0;
}

static PyObject *t_kind_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    t_kind *self = (t_kind *) type->tp_alloc(type, 0);

    if (self)
    {
        self->kind = NULL;
        self->flags = 0;
        self->descriptors = PyDict_New();
    }

    return (PyObject *) self;
}

static int t_kind_init(t_kind *self, PyObject *args, PyObject *kwds)
{
    PyObject *kind;

    if (!PyArg_ParseTuple(args, "O", &kind))
        return -1;

    Py_INCREF(kind);
    self->kind = (t_item *) kind;

    return 0;
}


static PyObject *t_kind_getAttribute(t_kind *self, PyObject *args)
{
    PyObject *item, *name;

    if (!PyArg_ParseTuple(args, "OO", &item, &name))
        return NULL;

    if (self->flags & DESCRIPTORS_INSTALLED)
    {
        t_descriptor *descriptor = (t_descriptor *)
            PyDict_GetItem(self->descriptors, name);

        if (descriptor)
        {
            t_attribute *attr = descriptor->attr;

            if (attr)
            {
                PyObject *view = ((t_item *) self->kind->root)->parent;
                return PyObject_GetItem(view, attr->attrID);
            }
        }
    }

    Py_RETURN_NONE;
}


/* monitorSchema */

static PyObject *t_kind_getMonitorSchema(t_kind *self, void *data)
{
    if (self->flags & MONITOR_SCHEMA)
        Py_RETURN_TRUE;

    Py_RETURN_FALSE;
}

static int t_kind_setMonitorSchema(t_kind *self, PyObject *arg, void *data)
{
    if (arg == Py_True)
        self->flags |= MONITOR_SCHEMA;
    else if (arg == Py_False)
        self->flags &= ~MONITOR_SCHEMA;
    else
    {
        PyErr_SetObject(PyExc_ValueError, arg);
        return -1;
    }

    return 0;
}


/* attributesCached */

static PyObject *t_kind_getAttributesCached(t_kind *self, void *data)
{
    if (self->flags & ATTRIBUTES_CACHED)
        Py_RETURN_TRUE;

    Py_RETURN_FALSE;
}

static int t_kind_setAttributesCached(t_kind *self, PyObject *arg, void *data)
{
    if (arg == Py_True)
        self->flags |= ATTRIBUTES_CACHED;
    else if (arg == Py_False)
        self->flags &= ~ATTRIBUTES_CACHED;
    else
    {
        PyErr_SetObject(PyExc_ValueError, arg);
        return -1;
    }

    return 0;
}


/* superKindsCached */

static PyObject *t_kind_getSuperKindsCached(t_kind *self, void *data)
{
    if (self->flags & SUPERKINDS_CACHED)
        Py_RETURN_TRUE;

    Py_RETURN_FALSE;
}

static int t_kind_setSuperKindsCached(t_kind *self, PyObject *arg, void *data)
{
    if (arg == Py_True)
        self->flags |= SUPERKINDS_CACHED;
    else if (arg == Py_False)
        self->flags &= ~SUPERKINDS_CACHED;
    else
    {
        PyErr_SetObject(PyExc_ValueError, arg);
        return -1;
    }

    return 0;
}


/* descriptorsInstalled */

static PyObject *t_kind_getDescriptorsInstalled(t_kind *self, void *data)
{
    if (self->flags & DESCRIPTORS_INSTALLED)
        Py_RETURN_TRUE;

    Py_RETURN_FALSE;
}

static int t_kind_setDescriptorsInstalled(t_kind *self, PyObject *arg,
                                          void *data)
{
    if (arg == Py_True)
        self->flags |= DESCRIPTORS_INSTALLED;
    else if (arg == Py_False)
        self->flags &= ~DESCRIPTORS_INSTALLED;
    else
    {
        PyErr_SetObject(PyExc_ValueError, arg);
        return -1;
    }

    return 0;
}


/* descriptorsInstalling */

static PyObject *t_kind_getDescriptorsInstalling(t_kind *self, void *data)
{
    if (self->flags & DESCRIPTORS_INSTALLING)
        Py_RETURN_TRUE;

    Py_RETURN_FALSE;
}

static int t_kind_setDescriptorsInstalling(t_kind *self, PyObject *arg,
                                          void *data)
{
    if (arg == Py_True)
        self->flags |= DESCRIPTORS_INSTALLING;
    else if (arg == Py_False)
        self->flags &= ~DESCRIPTORS_INSTALLING;
    else
    {
        PyErr_SetObject(PyExc_ValueError, arg);
        return -1;
    }

    return 0;
}


void _init_kind(PyObject *m)
{
    if (PyType_Ready(&KindType) >= 0)
    {
        if (m)
        {
            Py_INCREF(&KindType);
            PyModule_AddObject(m, "CKind", (PyObject *) &KindType);
        }
    }
}
