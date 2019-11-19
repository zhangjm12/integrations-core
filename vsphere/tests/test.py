from datadog_checks.vsphere import VSphereCheck


def test_vsphere(instance):
    check = VSphereCheck('vsphere', {}, [instance])
    import pdb; pdb.set_trace()
    check.check(instance)
