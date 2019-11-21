from datadog_checks.vsphere import VSphereCheck


def test_vsphere(instance):
    check = VSphereCheck('vsphere', {}, [instance])
    check.check(instance)
