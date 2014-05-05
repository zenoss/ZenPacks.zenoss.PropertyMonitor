/*****************************************************************************
 *
 * Copyright (C) Zenoss, Inc. 2013, all rights reserved.
 *
 * This content is made available according to terms specified in
 * License.zenoss under the directory where your Zenoss product is installed.
 *
 ****************************************************************************/

(function(){

var ZC = Ext.ns('Zenoss.component');
var router = Zenoss.remote.PropertyMonitorRouter;

Zenoss.form.ModelProperty = Ext.extend(Ext.Panel, {
    constructor: function(config) {
        config = config || {};
        var record = config.record, classNameStore,
            propertyNameStore;

        // Ext.version will be defined in ExtJS3 and undefined in ExtJS4.
        var storeClass = Ext.data.DirectStore        
        if (Ext.version === undefined) {
            storeClass = Zenoss.NonPaginatedStore
        }

        // store for the first combobox
        classNameStore = new storeClass({
            fields: ['key', 'label'],
            root: 'data',
            autoLoad: {
                params: {
                    query: 'record=' + record.uid
                },
                callback: function(){
                    this.ClassKeyCombo.setValue(record.class_name);
                },
                scope: this
            },
            directFn: router.getClasses
        });

        // store for the second combobox
        propertyNameStore = new storeClass({
            fields: ['key', 'label'],
            root: 'data',
            baseParams: {
                query: 'record=' + record.uid,
                class_name: record.class_name
            },
            autoLoad: {
                params: {
                    query: 'record=' + record.uid,
                    class_name: record.class_name
                },
                callback: function(){
                    this.CounterKeyCombo.setValue(record.property_name);
                },
                scope:this
            },
            directFn: router.getProperties
        });        

        Ext.apply(config, {
            border: false,
            items:[{
                xtype: 'combo',
                fieldLabel: _t('Class'),
                ref: 'ClassKeyCombo',
                name: 'class_name',
                triggerAction: 'all',
                listeners: {
                    select: this.updateProperties,
                    scope: this
                },
                queryMode: 'local',
                valueField: 'key',
                displayField: 'label',
                store: classNameStore
            },{
                xtype: 'combo',
                fieldLabel: _t('Counter'),
                name: 'property_name',
                ref: 'CounterKeyCombo',
                typeAhead: false,
                triggerAction: 'all',                
                queryMode: 'local',
                valueField: 'key',
                displayField: 'label',
                store: propertyNameStore
            }]
        });
        Zenoss.form.ModelProperty.superclass.constructor.apply(this, arguments);
    },
    /**
     * When the class changes this reloads the store for the property
     **/
    updateProperties: function () {
        var class_name = this.ClassKeyCombo.value,
        cmp = this.CounterKeyCombo;

        // reload the store
        cmp.getStore().load({
            params: {
                query: 'record=' + this.record.uid,
                class_name: class_name
            }        
        });
    }
});

// Ext.version will be defined in ExtJS3 and undefined in ExtJS4.
if (Ext.version === undefined) {
    Ext.reg('mbp_property', 'Zenoss.form.ModelProperty');
} else {
    Ext.reg('mbp_property', Zenoss.form.ModelProperty);
}

}());
